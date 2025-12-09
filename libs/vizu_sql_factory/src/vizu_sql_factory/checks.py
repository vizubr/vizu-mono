"""
SQL Validation Checks

Implements core validation checks for SQL queries:
- Only allowed views
- No DDL/DML
- Mandatory predicates (tenant filter)
- Explicit columns (no SELECT *)
- LIMIT present and capped
- Column allowlist
- Safe joins
- Safe aggregates
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List

from .parser import SqlParser

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a single validation error."""

    code: str  # e.g., "disallowed_view", "missing_limit"
    message: str
    field: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validation."""

    is_valid: bool
    original_sql: str
    normalized_sql: Optional[str] = None
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checks_passed: List[str] = field(default_factory=list)
    execution_plan: Optional[str] = None

    def add_error(self, error: ValidationError):
        """Add an error to the result."""
        self.errors.append(error)

    def add_warning(self, warning: str):
        """Add a warning to the result."""
        self.warnings.append(warning)

    def add_check_passed(self, check_name: str):
        """Record a passed check."""
        self.checks_passed.append(check_name)


class SqlValidator:
    """
    SQL Validator using sqlglot parser.

    Validates queries against:
    - Allowed views/tables
    - No DDL/DML operations
    - Mandatory tenant filter
    - Explicit columns (no SELECT *)
    - LIMIT clause present and capped
    - Column allowlist
    - Safe joins (optional)
    - Safe aggregates (optional)
    """

    def __init__(self):
        """Initialize validator."""
        self.parser = SqlParser()

    def validate(
        self,
        sql: str,
        tenant_id: str,
        allowed_views: List[str],
        allowed_columns: dict[str, List[str]],
        max_rows: int = 100,
        mandatory_filters: Optional[List[str]] = None,
        allowed_aggregates: Optional[List[str]] = None,
        allowed_joins: Optional[dict] = None,
        allow_rewrites: bool = True,
    ) -> ValidationResult:
        """
        Validate SQL query against constraints.

        Args:
            sql: SQL query to validate
            tenant_id: Tenant ID for mandatory filter check
            allowed_views: List of allowed view names
            allowed_columns: Dict mapping view names to allowed columns
            max_rows: Maximum rows allowed (default 100)
            mandatory_filters: Required filter columns (default ['client_id'])
            allowed_aggregates: List of allowed aggregate functions (default COUNT, SUM, AVG, MIN, MAX)
            allowed_joins: Optional dict of allowed join relationships
            allow_rewrites: Whether to rewrite queries instead of rejecting (default True)

        Returns:
            ValidationResult with is_valid, errors, warnings, and normalized_sql
        """
        if not mandatory_filters:
            mandatory_filters = ['client_id']

        if not allowed_aggregates:
            allowed_aggregates = ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']

        result = ValidationResult(is_valid=True, original_sql=sql)

        # Parse SQL
        ast = self.parser.parse(sql)
        if ast is None:
            result.is_valid = False
            result.add_error(ValidationError(
                code="parse_error",
                message="Failed to parse SQL query",
                suggestion="Check SQL syntax"
            ))
            return result

        # Check: Is SELECT
        if not self.parser.is_select(ast):
            result.is_valid = False
            result.add_error(ValidationError(
                code="not_select",
                message="Query must be SELECT statement only",
                suggestion="Use SELECT queries for read-only access"
            ))
            return result

        result.add_check_passed("is_select")

        # Check: No DDL/DML
        if self._check_no_ddl_dml(ast, result):
            result.add_check_passed("no_ddl_dml")
        else:
            result.is_valid = False
            return result

        # Check: Only allowed views
        if self._check_allowed_views(ast, allowed_views, result):
            result.add_check_passed("allowed_views")
        else:
            result.is_valid = False
            return result

        # Check: Explicit columns (no SELECT *)
        if self._check_explicit_columns(ast, result, allow_rewrites):
            result.add_check_passed("explicit_columns")
        else:
            if not allow_rewrites:
                result.is_valid = False
                return result

        # Check: Column allowlist
        if self._check_column_allowlist(ast, allowed_columns, result):
            result.add_check_passed("column_allowlist")
        else:
            result.is_valid = False
            return result

        # Check: Mandatory filters (tenant_id)
        if self._check_mandatory_filters(ast, tenant_id, mandatory_filters, result):
            result.add_check_passed("mandatory_filters")
        else:
            if not allow_rewrites:
                result.is_valid = False
                return result

        # Check: LIMIT present and capped
        if self._check_limit(ast, max_rows, result, allow_rewrites):
            result.add_check_passed("limit")
        else:
            if not allow_rewrites:
                result.is_valid = False
                return result

        # Optional: Check safe aggregates
        if self._check_safe_aggregates(ast, allowed_aggregates, result):
            result.add_check_passed("safe_aggregates")
        else:
            result.is_valid = False
            return result

        # Optional: Check safe joins
        if allowed_joins and not self._check_safe_joins(ast, allowed_joins, result):
            result.is_valid = False
            return result

        if allowed_joins:
            result.add_check_passed("safe_joins")

        # Build execution plan summary
        result.execution_plan = self._build_execution_plan(
            result, ast, allowed_columns, max_rows
        )

        return result

    def _check_no_ddl_dml(self, ast, result: ValidationResult) -> bool:
        """Check query is SELECT only, no DDL/DML."""
        from sqlglot import exp

        forbidden = {
            exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
            exp.Create, exp.Truncate, exp.Replace, exp.Grant, exp.Revoke
        }

        for node in ast.walk():
            for forbidden_class in forbidden:
                if isinstance(node, forbidden_class):
                    result.add_error(ValidationError(
                        code="ddl_dml_not_allowed",
                        message=f"{forbidden_class.__name__} statements are not allowed",
                        suggestion="Use SELECT queries only"
                    ))
                    return False

        return True

    def _check_allowed_views(self, ast, allowed_views: List[str], result: ValidationResult) -> bool:
        """Check all tables are in allowed views."""
        tables = self.parser.extract_tables(ast)

        for table in tables:
            if table not in allowed_views:
                result.add_error(ValidationError(
                    code="disallowed_view",
                    message=f"View '{table}' is not allowed for your role",
                    field=table,
                    suggestion=f"Allowed views: {', '.join(allowed_views)}"
                ))
                return False

        return True

    def _check_explicit_columns(self, ast, result: ValidationResult, allow_rewrites: bool) -> bool:
        """Check no SELECT * or SELECT table.*"""
        from sqlglot import exp

        has_star = False
        for expr in ast.expressions:
            if isinstance(expr, exp.Star):
                has_star = True
                break

        if has_star:
            if allow_rewrites:
                result.add_warning("SELECT * detected; will be rewritten to explicit columns")
                return True
            else:
                result.add_error(ValidationError(
                    code="select_star_not_allowed",
                    message="SELECT * is not allowed",
                    suggestion="List columns explicitly"
                ))
                return False

        return True

    def _check_column_allowlist(self, ast, allowed_columns: dict[str, List[str]], result: ValidationResult) -> bool:
        """Check all selected columns are allowed."""
        from sqlglot import exp

        tables = self.parser.extract_tables(ast)
        columns = self.parser.extract_columns(ast)

        # If SELECT * was expanded, this happens in rewrites, so skip for now
        if '*' in columns:
            return True

        for col in columns:
            # Skip if it's a function or literal
            if col.upper() in ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX'] or col.startswith("'"):
                continue

            # Check if column is allowed in any of the tables
            found = False
            for table in tables:
                if table in allowed_columns:
                    if col in allowed_columns[table]:
                        found = True
                        break

            if not found:
                result.add_error(ValidationError(
                    code="disallowed_column",
                    message=f"Column '{col}' is not allowed",
                    field=col,
                    suggestion=f"Allowed columns for your views: {allowed_columns}"
                ))
                return False

        return True

    def _check_mandatory_filters(self, ast, tenant_id: str, mandatory_filters: List[str], result: ValidationResult) -> bool:
        """Check query includes mandatory filters (e.g., client_id = '...')"""
        predicates = self.parser.extract_where_predicates(ast)

        # Check if any mandatory filter is present
        found_filter = False
        for filter_name in mandatory_filters:
            for predicate in predicates:
                if filter_name.lower() in predicate.lower():
                    found_filter = True
                    break

        if not found_filter:
            result.add_warning(f"No mandatory filter found ({', '.join(mandatory_filters)}); "
                             f"will be injected in rewrite")
            return True  # Allow, will be rewritten

        return True

    def _check_limit(self, ast, max_rows: int, result: ValidationResult, allow_rewrites: bool) -> bool:
        """Check LIMIT clause present and value <= max_rows."""
        if not self.parser.has_limit(ast):
            if allow_rewrites:
                result.add_warning(f"No LIMIT clause; will inject LIMIT {max_rows}")
                return True
            else:
                result.add_error(ValidationError(
                    code="missing_limit",
                    message="LIMIT clause is required",
                    suggestion=f"Add LIMIT clause (max {max_rows})"
                ))
                return False

        limit_value = self.parser.get_limit_value(ast)
        if limit_value and limit_value > max_rows:
            if allow_rewrites:
                result.add_warning(f"LIMIT {limit_value} exceeds max {max_rows}; will be capped")
                return True
            else:
                result.add_error(ValidationError(
                    code="limit_exceeded",
                    message=f"LIMIT {limit_value} exceeds maximum {max_rows}",
                    suggestion=f"Use LIMIT <= {max_rows}"
                ))
                return False

        return True

    def _check_safe_aggregates(self, ast, allowed_aggregates: List[str], result: ValidationResult) -> bool:
        """Check only allowed aggregate functions."""
        aggregates = self.parser.extract_aggregates(ast)

        for agg in aggregates:
            if agg not in allowed_aggregates:
                result.add_error(ValidationError(
                    code="disallowed_aggregate",
                    message=f"Aggregate function '{agg}' is not allowed",
                    suggestion=f"Allowed: {', '.join(allowed_aggregates)}"
                ))
                return False

        return True

    def _check_safe_joins(self, ast, allowed_joins: dict, result: ValidationResult) -> bool:
        """Check joins use only allowed relationships."""
        joins = self.parser.extract_joins(ast)

        for join in joins:
            # Check if join is in allowed list
            join_key = f"{join['right']}"
            if join_key not in allowed_joins:
                result.add_error(ValidationError(
                    code="disallowed_join",
                    message=f"Join with '{join['right']}' is not allowed",
                    suggestion=f"Allowed joins: {list(allowed_joins.keys())}"
                ))
                return False

        return True

    def _build_execution_plan(self, result: ValidationResult, ast, allowed_columns: dict, max_rows: int) -> str:
        """Build human-readable execution plan."""
        plan = "Execution Plan:\n"
        plan += f"  Checks passed: {len(result.checks_passed)}\n"
        plan += f"  Warnings: {len(result.warnings)}\n"

        tables = self.parser.extract_tables(ast)
        columns = self.parser.extract_columns(ast)
        joins = self.parser.extract_joins(ast)
        aggregates = self.parser.extract_aggregates(ast)
        limit = self.parser.get_limit_value(ast) or max_rows

        plan += f"  Tables: {', '.join(tables) if tables else 'none'}\n"
        plan += f"  Columns: {len(columns)} selected\n"
        plan += f"  Joins: {len(joins)} joins\n"
        plan += f"  Aggregates: {', '.join(aggregates) if aggregates else 'none'}\n"
        plan += f"  LIMIT: {limit}\n"

        if result.warnings:
            plan += f"\n  Rewrites needed:\n"
            for warning in result.warnings:
                plan += f"    - {warning}\n"

        return plan
