"""
Text-to-SQL Executor

Orchestrates the full SQL validation and execution pipeline:
1. Parse question → LLM to generate SQL
2. Validate SQL with SqlValidator (security, constraints)
3. Rewrite SQL for safety (SELECT *, LIMIT, tenant filter)
4. Execute via PostgRESTQueryExecutor (RLS enforcement)
5. Return results with telemetry

Reuses:
- vizu_supabase_client.PostgRESTQueryExecutor for safe query execution
- vizu_supabase_client.AuthContext for multi-tenant isolation
- vizu_supabase_client.JWTContextExtractor for JWT handling
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from uuid import uuid4

from vizu_supabase_client import (
    PostgRESTQueryExecutor,
    get_postgrest_executor,
    AuthContext,
)
from vizu_sql_factory.parser import SqlParser
from vizu_sql_factory.checks import SqlValidator, ValidationResult
from vizu_sql_factory.rewrites import SqlRewriter
from vizu_sql_factory.observability import SqlValidationObserver, ValidationTimer

logger = logging.getLogger(__name__)


@dataclass
class ExecutionConfig:
    """Configuration for SQL execution."""

    tenant_id: str
    allowed_views: List[str]
    allowed_columns: Dict[str, List[str]]
    max_rows: int = 100
    mandatory_filters: Optional[List[str]] = None
    allowed_aggregates: Optional[List[str]] = None
    allow_rewrites: bool = True
    tenant_column: str = "client_id"


@dataclass
class ExecutionResult:
    """Result from full SQL execution pipeline."""

    success: bool
    original_sql: str
    normalized_sql: Optional[str]
    rows: List[Dict[str, Any]]
    columns: List[Dict[str, str]]  # [{name, type}]
    row_count: int
    validation_result: Optional[ValidationResult] = None
    execution_time_ms: float = 0.0
    error: Optional[Dict[str, Any]] = None
    telemetry_id: str = ""
    caveats: List[str] = None

    def __post_init__(self):
        """Initialize defaults."""
        if self.caveats is None:
            self.caveats = []


class TextToSqlExecutor:
    """
    Orchestrates SQL validation and execution pipeline.

    Workflow:
    1. Validate SQL security & constraints (SqlValidator)
    2. Rewrite for safety (SqlRewriter)
    3. Execute via PostgREST (PostgRESTQueryExecutor)
    4. Return results with telemetry
    """

    def __init__(
        self,
        postgrest_executor: Optional[PostgRESTQueryExecutor] = None,
        observer: Optional[SqlValidationObserver] = None
    ):
        """
        Initialize executor.

        Args:
            postgrest_executor: PostgREST executor (default: singleton)
            observer: Validation observer for telemetry
        """
        self.postgrest_executor = postgrest_executor or get_postgrest_executor()
        self.observer = observer or SqlValidationObserver("text_to_sql_executor")
        self.parser = SqlParser()
        self.validator = SqlValidator()
        self.rewriter = SqlRewriter()

        logger.info("TextToSqlExecutor initialized")

    def execute(
        self,
        sql: str,
        config: ExecutionConfig,
        user_jwt: Optional[str] = None,
        auth_context: Optional[AuthContext] = None,
    ) -> ExecutionResult:
        """
        Execute SQL query with full validation and safety pipeline.

        Args:
            sql: SQL query to execute
            config: ExecutionConfig with tenant, allowlist, limits
            user_jwt: User JWT token for RLS enforcement
            auth_context: AuthContext (if provided, overrides config tenant_id)

        Returns:
            ExecutionResult with rows, columns, and telemetry
        """
        telemetry_id = str(uuid4())
        start_time = time.time()

        logger.info(
            f"[executor] Starting: tenant={config.tenant_id}, "
            f"telemetry_id={telemetry_id}"
        )

        try:
            # 1. Validate SQL
            with ValidationTimer("sql_validation", logger):
                validation_result = self.validator.validate(
                    sql=sql,
                    tenant_id=config.tenant_id,
                    allowed_views=config.allowed_views,
                    allowed_columns=config.allowed_columns,
                    max_rows=config.max_rows,
                    mandatory_filters=config.mandatory_filters or ["client_id"],
                    allowed_aggregates=config.allowed_aggregates,
                    allow_rewrites=config.allow_rewrites
                )

            if not validation_result.get("is_valid"):
                return self._build_error_result(
                    sql=sql,
                    validation_result=validation_result,
                    telemetry_id=telemetry_id,
                    start_time=start_time,
                    error_code="VALIDATION_ERROR",
                    error_msg="SQL validation failed"
                )

            # 2. Rewrite SQL for safety
            normalized_sql = sql
            if config.allow_rewrites:
                with ValidationTimer("sql_rewrites", logger):
                    normalized_sql = self.rewriter.apply_all_rewrites(
                        sql=validation_result.get("normalized_sql", sql),
                        tenant_id=config.tenant_id,
                        max_rows=config.max_rows,
                        allowed_columns=config.allowed_columns,
                        tenant_column=config.tenant_column
                    )

            logger.info(
                f"[executor] Validation passed, rewritten SQL: {normalized_sql[:100]}..."
            )

            # 3. Execute via PostgREST
            with ValidationTimer("postgrest_execution", logger):
                # For raw SQL execution, we need to use a different approach
                # PostgRESTQueryExecutor's query() method uses table-based queries
                # For arbitrary SQL, we'd need to create a view or use RPC
                # For now, we'll extract table and filters from validated SQL

                tables = self.parser.extract_tables(
                    self.parser.parse(normalized_sql)
                )

                if not tables:
                    raise ValueError("No tables found in SQL query")

                # Use first table (most queries have one main table)
                main_table = tables[0]

                # Build filters from WHERE clause
                filters = self._extract_filters_from_sql(normalized_sql)

                # Get columns from SELECT clause
                columns_from_sql = self.parser.extract_columns(
                    self.parser.parse(normalized_sql)
                )

                # Get limit
                limit = self.parser.get_limit_value(
                    self.parser.parse(normalized_sql)
                ) or config.max_rows

                logger.info(
                    f"[executor] Executing query: table={main_table}, "
                    f"filters={filters}, columns={columns_from_sql}, limit={limit}"
                )

                # Execute
                query_result = self.postgrest_executor.query(
                    view_name=main_table,
                    filters=filters,
                    columns=columns_from_sql if columns_from_sql else None,
                    limit=limit,
                    user_jwt=user_jwt,
                    count=False
                )

            # 4. Build result
            execution_time_ms = (time.time() - start_time) * 1000

            # Convert column names to column metadata
            columns_meta = [
                {"name": col, "type": "unknown"}  # TODO: Get real types from DB
                for col in query_result.column_names
            ]

            result = ExecutionResult(
                success=True,
                original_sql=sql,
                normalized_sql=normalized_sql,
                rows=query_result.rows,
                columns=columns_meta,
                row_count=len(query_result.rows),
                validation_result=validation_result,
                execution_time_ms=execution_time_ms,
                error=None,
                telemetry_id=telemetry_id,
                caveats=[
                    f"Query validated against {len(validation_result.get('checks_passed', []))} security checks",
                    f"Result limited to {limit} rows (config: {config.max_rows})",
                    f"Row-Level Security enforced via RLS policies"
                ]
            )

            logger.info(
                f"[executor] Success: {len(result.rows)} rows in "
                f"{execution_time_ms:.1f}ms, telemetry_id={telemetry_id}"
            )

            return result

        except Exception as e:
            logger.exception(f"[executor] Execution failed: {e}")
            execution_time_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                success=False,
                original_sql=sql,
                normalized_sql=None,
                rows=[],
                columns=[],
                row_count=0,
                validation_result=None,
                execution_time_ms=execution_time_ms,
                error={
                    "code": "EXECUTION_ERROR",
                    "message": str(e),
                    "suggestion": "Check logs for details"
                },
                telemetry_id=telemetry_id,
                caveats=[f"Execution failed: {str(e)}"]
            )

    def _extract_filters_from_sql(self, sql: str) -> Dict[str, Any]:
        """
        Extract WHERE clause conditions as filters.

        Args:
            sql: SQL query

        Returns:
            Dict mapping column -> value for PostgREST filters
        """
        ast = self.parser.parse(sql)
        if not ast:
            return {}

        predicates = self.parser.extract_where_predicates(ast)
        filters = {}

        # Simple extraction: parse predicates like "client_id = '123'"
        for pred in predicates:
            # Basic parsing; in production, use proper parser
            if "=" in pred and "'" in pred:
                parts = pred.split("=")
                if len(parts) == 2:
                    col = parts[0].strip()
                    val = parts[1].strip().replace("'", "").replace('"', '')
                    filters[col] = val

        return filters

    def _build_error_result(
        self,
        sql: str,
        validation_result: Dict[str, Any],
        telemetry_id: str,
        start_time: float,
        error_code: str,
        error_msg: str
    ) -> ExecutionResult:
        """Build error result from validation failure."""
        execution_time_ms = (time.time() - start_time) * 1000
        errors = validation_result.get("errors", [])

        error_dict = {
            "code": error_code,
            "message": error_msg,
            "validation_errors": [
                {
                    "code": e.get("code"),
                    "message": e.get("message"),
                    "suggestion": e.get("suggestion")
                }
                for e in errors
            ] if isinstance(errors, list) else []
        }

        return ExecutionResult(
            success=False,
            original_sql=sql,
            normalized_sql=None,
            rows=[],
            columns=[],
            row_count=0,
            validation_result=validation_result,
            execution_time_ms=execution_time_ms,
            error=error_dict,
            telemetry_id=telemetry_id,
            caveats=[
                f"Validation failed: {len(errors)} errors",
                validation_result.get("execution_plan", "")
            ]
        )
