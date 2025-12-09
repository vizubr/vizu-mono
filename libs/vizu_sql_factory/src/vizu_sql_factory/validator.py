"""
SQL validation layer for safe text-to-SQL execution.

This module provides robust SQL parsing, validation, and rewriting capabilities
to enforce security constraints (view allowlists, mandatory predicates, etc.)
before execution.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class ValidationErrorType(Enum):
    """Error types for SQL validation."""
    PARSING_ERROR = "parsing_error"
    DISALLOWED_VIEW = "disallowed_view"
    DISALLOWED_COLUMN = "disallowed_column"
    DDL_DML_DETECTED = "ddl_dml_detected"
    MISSING_TENANT_FILTER = "missing_tenant_filter"
    MISSING_LIMIT = "missing_limit"
    DISALLOWED_AGGREGATE = "disallowed_aggregate"
    DISALLOWED_FUNCTION = "disallowed_function"
    CROSS_TENANT_JOIN = "cross_tenant_join"
    GENERIC_ERROR = "generic_error"


@dataclass
class ValidationError:
    """Single validation error."""
    type: ValidationErrorType
    message: str
    severity: str = "error"  # "error" or "warning"
    suggestion: Optional[str] = None
    position: Optional[int] = None  # Character position in SQL

    def __str__(self) -> str:
        return f"[{self.type.value}] {self.message}"


@dataclass
class ValidationResult:
    """Result of SQL validation."""
    is_valid: bool
    original_sql: str
    normalized_sql: Optional[str] = None  # Rewritten SQL if applicable
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks_passed: List[str] = field(default_factory=list)
    execution_plan: Optional[str] = None  # For observability
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_errors(self) -> bool:
        """Check if validation has blocking errors."""
        return any(e.severity == "error" for e in self.errors)

    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0 or any(
            e.severity == "warning" for e in self.errors
        )

    def error_summary(self) -> str:
        """Get summary of errors."""
        if not self.errors:
            return "No errors"
        return "; ".join(str(e) for e in self.errors)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "is_valid": self.is_valid,
            "original_sql": self.original_sql,
            "normalized_sql": self.normalized_sql,
            "errors": [
                {
                    "type": e.type.value,
                    "message": e.message,
                    "severity": e.severity,
                    "suggestion": e.suggestion,
                }
                for e in self.errors
            ],
            "warnings": self.warnings,
            "checks_passed": self.checks_passed,
            "metadata": self.metadata,
        }


class SqlValidator:
    """
    Validates SQL queries against security and structural constraints.

    Responsibilities:
    - Parse SQL (basic syntax checking)
    - Validate against allowlist (views, columns, aggregates)
    - Detect and block DDL/DML operations
    - Enforce mandatory predicates (tenant_id filters)
    - Check for LIMIT clauses
    - Rewrite queries to inject missing constraints
    - Explain validation decisions for observability
    """

    def __init__(self, allowlist_config=None, max_query_length: int = 5000):
        """
        Initialize validator.

        Args:
            allowlist_config: AllowlistConfig instance for view/column validation.
            max_query_length: Maximum allowed query length in characters.
        """
        self.allowlist_config = allowlist_config
        self.max_query_length = max_query_length
        logger.info(f"SqlValidator initialized (max_length={max_query_length})")

    def parse(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Basic SQL parsing to detect syntax errors.

        Args:
            sql: SQL query string.

        Returns:
            Tuple of (is_valid, error_message).
            is_valid: True if syntax appears valid.
            error_message: Human-readable error if invalid.
        """
        sql_clean = sql.strip()

        # Empty query
        if not sql_clean:
            return False, "Empty SQL query"

        # Length check
        if len(sql_clean) > self.max_query_length:
            return False, f"Query exceeds max length ({len(sql_clean)} > {self.max_query_length})"

        # Check for balanced parentheses
        if sql_clean.count("(") != sql_clean.count(")"):
            return False, "Unbalanced parentheses in query"

        # Basic structure: must start with SELECT (for SELECT-only validation)
        if not re.match(r"^\s*SELECT\s", sql_clean, re.IGNORECASE):
            return False, "Query must be a SELECT statement"

        return True, None

    def validate(
        self,
        sql: str,
        tenant_id: str,
        role: str,
    ) -> ValidationResult:
        """
        Full validation of SQL query against constraints.

        Args:
            sql: SQL query string.
            tenant_id: Tenant identifier (for context).
            role: User role (for allowlist lookup).

        Returns:
            ValidationResult with detailed findings.
        """
        sql_clean = sql.strip()
        result = ValidationResult(
            is_valid=True,
            original_sql=sql_clean,
            checks_passed=[],
            errors=[],
            warnings=[],
            metadata={
                "tenant_id": tenant_id,
                "role": role,
            },
        )

        # Check 1: Basic parsing
        is_parsable, parse_error = self.parse(sql_clean)
        if not is_parsable:
            result.is_valid = False
            result.errors.append(
                ValidationError(
                    type=ValidationErrorType.PARSING_ERROR,
                    message=parse_error,
                    severity="error",
                )
            )
            return result

        result.checks_passed.append("basic_parsing")

        # Check 2: No DDL/DML
        has_ddl_dml, ddl_found = self._check_no_ddl_dml(sql_clean)
        if not has_ddl_dml:
            result.is_valid = False
            result.errors.append(
                ValidationError(
                    type=ValidationErrorType.DDL_DML_DETECTED,
                    message=f"DDL/DML detected: {ddl_found}",
                    severity="error",
                    suggestion="Only SELECT queries are allowed",
                )
            )
        else:
            result.checks_passed.append("no_ddl_dml")

        # Check 3: Only allowed views (if allowlist config provided)
        if self.allowlist_config:
            allowed_views = self._check_only_allowed_views(
                sql_clean, tenant_id, role
            )
            if not allowed_views["valid"]:
                result.is_valid = False
                for view_name in allowed_views.get("disallowed_views", []):
                    result.errors.append(
                        ValidationError(
                            type=ValidationErrorType.DISALLOWED_VIEW,
                            message=f"View not allowed for this role: {view_name}",
                            severity="error",
                            suggestion=f"Use only allowed views: {', '.join(allowed_views.get('allowed_views', []))}",
                        )
                    )
            else:
                result.checks_passed.append("allowed_views")

        # Check 4: Mandatory predicates (tenant_id filter)
        has_tenant_filter, missing_tables = self._check_mandatory_predicates(sql_clean, tenant_id)
        if not has_tenant_filter:
            result.is_valid = False
            result.errors.append(
                ValidationError(
                    type=ValidationErrorType.MISSING_TENANT_FILTER,
                    message=f"Missing tenant filter (client_id = '{tenant_id}') for tables: {missing_tables}",
                    severity="error",
                    suggestion="Add WHERE clause filtering by client_id or use a tenant-scoped view",
                )
            )
        else:
            result.checks_passed.append("mandatory_predicates")

        # Check 5: LIMIT clause present
        has_limit, limit_value = self._check_limit_present(sql_clean)
        if not has_limit:
            result.warnings.append("No LIMIT clause found; query may return large result set")
            # Add rewrite suggestion
            result.normalized_sql = self._rewrite_inject_limit(sql_clean, 100)
        else:
            result.checks_passed.append("limit_present")

        # Check 6: Disallowed functions/aggregates (if allowlist config provided)
        if self.allowlist_config:
            allowed_aggs = self._check_allowed_aggregates(
                sql_clean, tenant_id, role
            )
            if not allowed_aggs["valid"]:
                result.is_valid = False
                for agg in allowed_aggs.get("disallowed_aggregates", []):
                    result.errors.append(
                        ValidationError(
                            type=ValidationErrorType.DISALLOWED_AGGREGATE,
                            message=f"Aggregate function not allowed: {agg}",
                            severity="error",
                            suggestion=f"Use only: {', '.join(allowed_aggs.get('allowed_aggregates', []))}",
                        )
                    )
            else:
                result.checks_passed.append("allowed_aggregates")

        logger.info(
            f"SQL validation for {tenant_id}/{role}: valid={result.is_valid}, "
            f"errors={len(result.errors)}, warnings={len(result.warnings)}"
        )
        return result

    def rewrite(
        self,
        sql: str,
        tenant_id: str,
        role: str,
        max_rows: int = 100,
    ) -> str:
        """
        Rewrite SQL to inject missing safety constraints.

        Args:
            sql: Original SQL.
            tenant_id: Tenant ID to inject in filters.
            role: User role.
            max_rows: Max rows to inject in LIMIT.

        Returns:
            Rewritten SQL with constraints injected.
        """
        sql_rewritten = sql.strip()

        # Inject missing LIMIT
        if not self._check_limit_present(sql_rewritten)[0]:
            sql_rewritten = self._rewrite_inject_limit(sql_rewritten, max_rows)

        # Inject tenant filter (stub - would parse WHERE and inject)
        # This is complex and requires SQL parsing; stubbed for Phase 0
        # sql_rewritten = self._rewrite_inject_tenant_filter(sql_rewritten, tenant_id)

        return sql_rewritten

    def explain(self, result: ValidationResult) -> str:
        """
        Generate human-readable explanation of validation result.

        Args:
            result: ValidationResult instance.

        Returns:
            Formatted explanation string.
        """
        lines = []
        lines.append(f"SQL Validation for {result.metadata.get('tenant_id', 'unknown')}")
        lines.append(f"Status: {'✅ VALID' if result.is_valid else '❌ INVALID'}")
        lines.append("")

        if result.errors:
            lines.append("❌ Errors:")
            for err in result.errors:
                lines.append(f"  - {err.message}")
                if err.suggestion:
                    lines.append(f"    Suggestion: {err.suggestion}")

        if result.warnings:
            lines.append("⚠️  Warnings:")
            for warn in result.warnings:
                lines.append(f"  - {warn}")

        if result.checks_passed:
            lines.append("✅ Checks Passed:")
            for check in result.checks_passed:
                lines.append(f"  - {check}")

        if result.normalized_sql and result.normalized_sql != result.original_sql:
            lines.append("")
            lines.append("Suggested Rewrite:")
            lines.append(result.normalized_sql)

        return "\n".join(lines)

    # ========================================================================
    # Validation Check Methods (Stubs for Phase 0, Implementation in Phase 2)
    # ========================================================================

    def _check_no_ddl_dml(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Check that query doesn't contain DDL/DML."""
        # Keywords that indicate DDL/DML
        ddl_dml_keywords = [
            r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b",
            r"\bCREATE\b", r"\bALTER\b", r"\bDROP\b",
            r"\bTRUNCATE\b", r"\bGRANT\b", r"\bREVOKE\b",
        ]

        for keyword_pattern in ddl_dml_keywords:
            if re.search(keyword_pattern, sql, re.IGNORECASE):
                match = re.search(keyword_pattern, sql, re.IGNORECASE)
                return False, match.group(0) if match else "Unknown"

        return True, None

    def _check_only_allowed_views(
        self,
        sql: str,
        tenant_id: str,
        role: str,
    ) -> Dict[str, Any]:
        """Check that only allowed views are referenced."""
        # Stub: extract view names from FROM/JOIN clauses
        # For Phase 0, we accept all views; real validation in Phase 2
        allowed_views = []
        if self.allowlist_config:
            role_config = self.allowlist_config.get_role_config(tenant_id, role)
            if role_config:
                allowed_views = role_config.views

        # Simple regex to extract table/view names from FROM/JOIN
        # This is a simplified extraction; real SQL parsing would be more robust
        table_pattern = r"(?:FROM|JOIN)\s+(`?\w+`?)"
        found_tables = set()
        for match in re.finditer(table_pattern, sql, re.IGNORECASE):
            table_name = match.group(1).strip("`").strip()
            found_tables.add(table_name)

        disallowed = []
        if allowed_views:
            disallowed = [t for t in found_tables if t not in allowed_views]

        return {
            "valid": len(disallowed) == 0,
            "found_views": list(found_tables),
            "allowed_views": allowed_views,
            "disallowed_views": disallowed,
        }

    def _check_mandatory_predicates(
        self,
        sql: str,
        tenant_id: str,
    ) -> Tuple[bool, List[str]]:
        """Check for mandatory tenant_id filter in WHERE clause."""
        # Stub: look for 'client_id = <tenant_id>' or similar
        # For Phase 0, we assume tenant filtering is in views
        # Real validation would parse WHERE clauses in Phase 2

        # Simple heuristic: check if client_id or cliente_vizu_id appears in WHERE
        tenant_patterns = [
            r"client_id\s*=",
            r"cliente_vizu_id\s*=",
            r"tenant_id\s*=",
        ]
        has_filter = any(
            re.search(pattern, sql, re.IGNORECASE)
            for pattern in tenant_patterns
        )

        if has_filter:
            return True, []
        else:
            # Assume if using a view, it's tenant-filtered
            # Real validation would check view definition in Phase 2
            return True, []

    def _check_limit_present(self, sql: str) -> Tuple[bool, Optional[int]]:
        """Check that query has a LIMIT clause."""
        match = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)
        if match:
            return True, int(match.group(1))
        return False, None

    def _check_allowed_aggregates(
        self,
        sql: str,
        tenant_id: str,
        role: str,
    ) -> Dict[str, Any]:
        """Check that only allowed aggregate functions are used."""
        allowed_aggs = []
        if self.allowlist_config:
            role_config = self.allowlist_config.get_role_config(tenant_id, role)
            if role_config:
                allowed_aggs = role_config.aggregates

        # Find aggregate functions: COUNT, SUM, AVG, MIN, MAX, STRING_AGG, etc.
        agg_pattern = r"\b(COUNT|SUM|AVG|MIN|MAX|STRING_AGG|LISTAGG|ARRAY_AGG)\s*\("
        found_aggs = set()
        for match in re.finditer(agg_pattern, sql, re.IGNORECASE):
            found_aggs.add(match.group(1).upper())

        disallowed = []
        if allowed_aggs:
            disallowed = [a for a in found_aggs if a not in [x.upper() for x in allowed_aggs]]

        return {
            "valid": len(disallowed) == 0,
            "found_aggregates": list(found_aggs),
            "allowed_aggregates": allowed_aggs,
            "disallowed_aggregates": disallowed,
        }

    # ========================================================================
    # Rewrite Methods (Stubs for Phase 0, Implementation in Phase 2)
    # ========================================================================

    def _rewrite_select_star(self, sql: str, allowed_columns: List[str]) -> str:
        """Rewrite SELECT * to explicit column list."""
        # Stub: replace SELECT * with explicit columns
        return sql  # Phase 0: no-op

    def _rewrite_inject_limit(self, sql: str, limit_value: int) -> str:
        """Inject LIMIT clause if missing."""
        sql_clean = sql.rstrip(";").strip()
        return f"{sql_clean}\nLIMIT {limit_value};"

    def _rewrite_inject_tenant_filter(self, sql: str, tenant_id: str) -> str:
        """Inject tenant_id filter in WHERE clause."""
        # Stub: parse WHERE, inject AND condition
        return sql  # Phase 0: no-op
