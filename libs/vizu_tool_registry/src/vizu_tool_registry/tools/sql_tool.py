"""
Text-to-SQL Tool Definition

This module defines the MCP tool for safe SQL query generation and execution.
It serves as the interface contract between the LLM and the query executor.

Phase 0: Base tool definition with mock invoke() - stubs ready for Phase 1
Phase 1: Real implementation with prompt builder + LLM + validator + executor
         Integrates vizu_sql_factory (schema, validator) + vizu_supabase_client (executor)
"""

import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from enum import Enum
from uuid import uuid4
from datetime import datetime

logger = logging.getLogger(__name__)


class SQLToolError(Enum):
    """
    Error codes for SQL tool execution.

    Error codes follow Phase 4 specifications:
    - llm_unable: LLM could not generate valid SQL
    - validation_failed: Generated SQL fails safety constraints
    - rls_denied: Row-level security blocked the query
    - execution_timeout: Query exceeded time limit
    - schema_unavailable: Schema metadata not available
    - internal_error: Unexpected internal error
    """
    LLM_UNABLE = "llm_unable"
    VALIDATION_FAILED = "validation_failed"
    RLS_DENIED = "rls_denied"
    EXECUTION_TIMEOUT = "execution_timeout"
    SCHEMA_UNAVAILABLE = "schema_unavailable"
    INTERNAL_ERROR = "internal_error"

    # Legacy error codes (for backwards compatibility)
    PARSING_ERROR = "llm_unable"
    VALIDATION_ERROR = "validation_failed"
    EXECUTION_ERROR = "internal_error"
    AUTHORIZATION_ERROR = "rls_denied"
    NOT_FOUND = "schema_unavailable"
    RATE_LIMIT = "internal_error"
    TIMEOUT = "execution_timeout"
    UNKNOWN = "internal_error"


@dataclass
class SQLToolInput:
    """Input parameters for the SQL tool."""
    question: str  # Natural language question
    tenant_id: str  # Tenant identifier (from JWT context)
    role: str  # User role (from JWT context)
    optional_constraints: Optional[Dict[str, Any]] = None  # e.g., {"date_range": "last_30_days", "max_rows": 100}
    user_jwt: Optional[str] = None  # User JWT token for RLS enforcement

    def validate(self) -> bool:
        """Validate input parameters."""
        return bool(self.question and self.tenant_id and self.role)


@dataclass
class SQLToolOutput:
    """Output from the SQL tool."""
    success: bool  # Whether query succeeded
    sql: Optional[str] = None  # Generated/validated SQL or null if failed
    rows: List[Dict[str, Any]] = None  # Query results or empty list
    columns: List[Dict[str, Any]] = None  # Column metadata: [{"name": "...", "type": "..."}]
    caveats: List[str] = None  # Execution notes (e.g., "Result limited to 100 rows")
    error: Optional[Dict[str, Any]] = None  # Structured error if failed
    telemetry_id: Optional[str] = None  # UUID for tracing
    execution_time_ms: Optional[float] = None  # Query execution time

    def __post_init__(self):
        """Initialize defaults."""
        if self.rows is None:
            self.rows = []
        if self.columns is None:
            self.columns = []
        if self.caveats is None:
            self.caveats = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "sql": self.sql,
            "rows": self.rows,
            "columns": self.columns,
            "caveats": self.caveats,
            "error": self.error,
            "telemetry_id": self.telemetry_id,
            "execution_time_ms": self.execution_time_ms,
        }


class QueryDatabaseTextToSQL:
    """
    MCP Tool: Query Database via Text-to-SQL

    Translates natural language questions into SQL queries, validates them
    against security constraints, and executes them via PostgREST with
    Row-Level Security (RLS) enforcement.

    Tool Name: query_database_text_to_sql
    """

    NAME = "query_database_text_to_sql"
    DESCRIPTION = (
        "Execute analytical queries on the database using natural language. "
        "Translates questions to SQL, validates safety constraints, and returns results."
    )

    # Tool schema (input parameters)
    INPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Natural language question to ask the database. "
                "Examples: 'How many customers signed up last month?', "
                "'List the top 10 products by revenue'.",
                "minLength": 5,
                "maxLength": 500,
            },
            "tenant_id": {
                "type": "string",
                "description": "Tenant/organization identifier. Extracted from JWT context at runtime. "
                "Used to enforce multi-tenant isolation.",
                "format": "uuid",
            },
            "role": {
                "type": "string",
                "enum": ["viewer", "analyst", "admin"],
                "description": "User role determining query scope and row limits. "
                "Extracted from JWT context at runtime.",
            },
            "optional_constraints": {
                "type": "object",
                "description": "Optional query constraints. Examples: "
                "{'date_range': 'last_30_days', 'max_rows': 500, 'customer_segment': 'premium'}",
                "properties": {
                    "date_range": {
                        "type": "string",
                        "enum": ["last_7_days", "last_30_days", "last_90_days", "year_to_date"],
                    },
                    "max_rows": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100000,
                    },
                    "customer_segment": {
                        "type": "string",
                    },
                },
            },
        },
        "required": ["question", "tenant_id", "role"],
    }

    # Tool schema (output)
    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether query succeeded (true) or failed (false).",
            },
            "sql": {
                "type": ["string", "null"],
                "description": "Validated SQL query executed. Null if validation failed.",
            },
            "rows": {
                "type": "array",
                "description": "Query result rows (list of dictionaries).",
                "items": {"type": "object"},
            },
            "columns": {
                "type": "array",
                "description": "Column metadata including name and type.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                    },
                },
            },
            "caveats": {
                "type": "array",
                "description": "Execution notes (e.g., 'Result limited to 100 rows', 'Cross-tenant queries blocked').",
                "items": {"type": "string"},
            },
            "error": {
                "type": ["object", "null"],
                "description": "Structured error if failed (null if successful).",
                "properties": {
                    "code": {
                        "type": "string",
                        "enum": [e.value for e in SQLToolError],
                    },
                    "message": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
            },
            "telemetry_id": {
                "type": "string",
                "description": "UUID for tracing logs and analysis.",
            },
            "execution_time_ms": {
                "type": "number",
                "description": "Query execution time in milliseconds.",
            },
        },
        "required": ["success", "sql", "rows", "columns", "caveats", "error", "telemetry_id"],
    }

    def __init__(self):
        """Initialize the tool."""
        logger.info(f"Initialized tool: {self.NAME}")
        self._error_messages = self._build_error_messages()

    def _build_error_messages(self) -> Dict[str, Dict[str, str]]:
        """
        Build error messages and suggestions for all error codes.

        Returns:
            Dict mapping error code to message and suggestion.
        """
        return {
            SQLToolError.LLM_UNABLE.value: {
                "message": (
                    "The AI language model was unable to formulate a query. "
                    "This may indicate the question is outside the scope of available data or is too ambiguous."
                ),
                "suggestion": (
                    "Try rephrasing your question more specifically. "
                    "Include date ranges, specific metrics, or mention the tables you're interested in. "
                    "Example: Instead of 'show me data', try 'how many orders were placed in the last 30 days?'"
                ),
            },
            SQLToolError.VALIDATION_FAILED.value: {
                "message": (
                    "The generated SQL does not meet safety constraints. "
                    "The query may reference restricted views or columns, "
                    "or may not include required security filters."
                ),
                "suggestion": (
                    "Check the details below for specific constraints violated. "
                    "Available views for your role are: {available_views}. "
                    "Try asking about those instead, or contact your administrator for access."
                ),
            },
            SQLToolError.RLS_DENIED.value: {
                "message": (
                    "Access to the requested data is denied by security policies. "
                    "Your role or tenant restrictions prevent you from accessing this data."
                ),
                "suggestion": (
                    "You may not have permission to view this data in your current role. "
                    "Contact your administrator if this is unexpected."
                ),
            },
            SQLToolError.EXECUTION_TIMEOUT.value: {
                "message": (
                    "Query execution timed out after 30 seconds. "
                    "The query is requesting too much data or performing too many complex operations."
                ),
                "suggestion": (
                    "Try narrowing the query scope: "
                    "1. Specify a specific date range (e.g., 'last 7 days' instead of 'all time'). "
                    "2. Reduce the number of rows (e.g., 'top 10' instead of 'all'). "
                    "3. Ask about specific tables or metrics. "
                    "4. Contact support for very large dataset requests."
                ),
            },
            SQLToolError.SCHEMA_UNAVAILABLE.value: {
                "message": (
                    "Schema metadata is temporarily unavailable. "
                    "The system cannot access the database schema right now."
                ),
                "suggestion": (
                    "This is a temporary issue. Try again in a moment. "
                    "If the issue persists, contact support with the telemetry ID below."
                ),
            },
            SQLToolError.INTERNAL_ERROR.value: {
                "message": (
                    "An internal error occurred. "
                    "This is likely a server-side issue, not a problem with your query."
                ),
                "suggestion": (
                    "Please contact support with the telemetry ID below so we can investigate. "
                    "Telemetry ID: {telemetry_id}"
                ),
            },
        }


    @classmethod
    def get_tool_definition(cls) -> Dict[str, Any]:
        """
        Get the tool definition for MCP registration.

        Returns:
            Tool definition dict with name, description, and schemas.
        """
        return {
            "name": cls.NAME,
            "description": cls.DESCRIPTION,
            "inputSchema": cls.INPUT_SCHEMA,
            "outputSchema": cls.OUTPUT_SCHEMA,
        }

    def invoke(self, input_params: SQLToolInput) -> SQLToolOutput:
        """
        Invoke the tool with input parameters.

        Pipeline:
        1. Generate SQL from question via LLM
        2. Validate SQL security constraints (SqlValidator)
        3. Rewrite for safety (SqlRewriter)
        4. Execute via PostgREST with RLS (PostgRESTQueryExecutor)
        5. Sanitize results (ResultSanitizer)
        6. Return SQLToolOutput

        Args:
            input_params: SQLToolInput with question, tenant_id, role.

        Returns:
            SQLToolOutput with results or error.
        """
        from vizu_sql_factory import (
            TextToSqlPrompt,
            TextToSqlExecutor,
            ExecutionConfig,
            ResultSanitizer,
        )
        from vizu_llm_service import get_model, ModelTier

        telemetry_id = str(uuid4())
        start_time = datetime.now()

        try:
            # 1. Validate input
            if not input_params.validate():
                logger.error(f"Invalid input: {input_params}")
                return SQLToolOutput(
                    success=False,
                    sql=None,
                    rows=[],
                    columns=[],
                    caveats=["Input validation failed"],
                    error={
                        "code": SQLToolError.LLM_UNABLE.value,
                        "message": "Invalid input parameters: missing question, tenant_id, or role",
                        "suggestion": "Provide all required parameters",
                    },
                    telemetry_id=telemetry_id,
                    execution_time_ms=0.0,
                )

            logger.info(
                f"[sql_tool] Invoked: question='{input_params.question[:50]}...', "
                f"tenant={input_params.tenant_id}, role={input_params.role}, "
                f"telemetry_id={telemetry_id}"
            )

            # 2. Get LLM for SQL generation
            try:
                llm = get_model(
                    tier=ModelTier.DEFAULT,
                    task="text_to_sql",
                    user_id=str(input_params.tenant_id),
                    tags=["tool_pool", "sql_tool", f"role_{input_params.role}"],
                )
            except Exception as e:
                logger.error(f"Failed to get LLM: {e}")
                return self._error_result(
                    telemetry_id, start_time,
                    SQLToolError.SCHEMA_UNAVAILABLE,
                    message=f"Failed to initialize language model: {str(e)}"
                )

            # 3. Generate SQL from question
            try:
                prompt = TextToSqlPrompt.build()
                sql = llm.invoke(prompt.build_from_context(
                    question=input_params.question,
                    tenant_id=input_params.tenant_id,
                    role=input_params.role,
                ))

                if not sql or not isinstance(sql, str):
                    logger.error(f"LLM returned invalid SQL: {sql}")
                    return self._error_result(
                        telemetry_id, start_time,
                        SQLToolError.LLM_UNABLE,
                        message="The AI language model could not generate valid SQL from your question."
                    )

                logger.info(f"[sql_tool] Generated SQL: {sql[:100]}...")
            except Exception as e:
                logger.exception(f"Failed to generate SQL: {e}")
                return self._error_result(
                    telemetry_id, start_time,
                    SQLToolError.LLM_UNABLE,
                    message=f"Failed to generate SQL: {str(e)}"
                )

            # 4. Set up execution config based on role
            role_config = self._get_role_config(input_params.role)
            config = ExecutionConfig(
                tenant_id=input_params.tenant_id,
                allowed_views=role_config["allowed_views"],
                allowed_columns=role_config["allowed_columns"],
                max_rows=role_config["max_rows"],
                mandatory_filters=["client_id"],
                allow_rewrites=True,
                tenant_column="client_id",
            )

            # 5. Execute with validation, rewriting, and sanitization
            executor = TextToSqlExecutor()
            exec_result = executor.execute(
                sql=sql,
                config=config,
                user_jwt=input_params.user_jwt,
            )

            if not exec_result.success:
                logger.warning(f"[sql_tool] Execution failed: {exec_result.error}")
                return SQLToolOutput(
                    success=False,
                    sql=sql,
                    rows=[],
                    columns=[],
                    caveats=exec_result.caveats,
                    error=exec_result.error,
                    telemetry_id=telemetry_id,
                    execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # 6. Sanitize results
            sanitizer = ResultSanitizer()
            sanitized = sanitizer.sanitize(
                rows=exec_result.rows,
                columns=exec_result.columns,
                allowed_columns=config.allowed_columns,
                mask_pii=True,
            )

            # Apply row limits per role
            sanitized_rows, size_caveats = sanitizer.filter_large_results(
                rows=sanitized["rows"],
                max_rows=role_config["max_rows"],
                max_cell_size=1000,
            )

            # 7. Build output
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

            all_caveats = (
                exec_result.caveats +
                sanitized["caveats"] +
                size_caveats
            )

            result = SQLToolOutput(
                success=True,
                sql=exec_result.normalized_sql or sql,
                rows=sanitized_rows,
                columns=sanitized["columns"],
                caveats=all_caveats,
                error=None,
                telemetry_id=telemetry_id,
                execution_time_ms=execution_time_ms,
            )

            logger.info(
                f"[sql_tool] Success: {len(sanitized_rows)} rows, "
                f"{len(sanitized['columns'])} cols, {execution_time_ms:.1f}ms"
            )
            return result

        except Exception as e:
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.exception(f"[sql_tool] Unexpected error: {e}")
            return SQLToolOutput(
                success=False,
                sql=None,
                rows=[],
                columns=[],
                caveats=[],
                error={
                    "code": SQLToolError.UNKNOWN.value,
                    "message": f"Unexpected error: {str(e)}",
                    "suggestion": "Check logs for details",
                },
                telemetry_id=telemetry_id,
                execution_time_ms=execution_time_ms,
            )

    def _get_role_config(self, role: str) -> Dict[str, Any]:
        """Get allowed views/columns by role."""
        # TODO: Load from allowlist config or environment
        # For now, return default permissive config
        return {
            "allowed_views": [
                "customers", "orders", "products", "transactions",
                "users", "invoices", "payments", "inventory"
            ],
            "allowed_columns": {
                "customers": ["id", "name", "email", "created_at", "status", "client_id"],
                "orders": ["id", "customer_id", "total", "status", "created_at", "client_id"],
                "products": ["id", "name", "price", "category", "client_id"],
                "transactions": ["id", "customer_id", "amount", "type", "created_at", "client_id"],
                "users": ["id", "name", "email", "role", "client_id"],
                "invoices": ["id", "customer_id", "amount", "due_date", "client_id"],
                "payments": ["id", "invoice_id", "amount", "date", "client_id"],
                "inventory": ["id", "product_id", "quantity", "warehouse", "client_id"],
            },
            "max_rows": self._get_max_rows_by_role(role),
        }

    def _get_max_rows_by_role(self, role: str) -> int:
        """Get max rows by role."""
        role_limits = {
            "viewer": 100,
            "analyst": 10000,
            "admin": 100000,
        }
        return role_limits.get(role, 100)

    def _error_result(
        self,
        telemetry_id: str,
        start_time: datetime,
        error_code: SQLToolError,
        message: Optional[str] = None,
        suggestion: Optional[str] = None,
        available_views: Optional[List[str]] = None,
    ) -> SQLToolOutput:
        """
        Build error result with standardized error messages and suggestions.

        Args:
            telemetry_id: Unique identifier for this error.
            start_time: When this operation started (for timing).
            error_code: Error code from SQLToolError enum.
            message: Optional override for error message.
            suggestion: Optional override for suggestion.
            available_views: Optional list of available views for context.

        Returns:
            SQLToolOutput with error details.
        """
        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Use standardized messages if not overridden
        error_info = self._error_messages.get(error_code.value, {})
        final_message = message or error_info.get("message", str(error_code.value))
        final_suggestion = suggestion or error_info.get("suggestion", "")

        # Format suggestion with context if available
        if "{available_views}" in final_suggestion and available_views:
            final_suggestion = final_suggestion.format(
                available_views=", ".join(available_views)
            )
        if "{telemetry_id}" in final_suggestion:
            final_suggestion = final_suggestion.format(telemetry_id=telemetry_id)

        return SQLToolOutput(
            success=False,
            sql=None,
            rows=[],
            columns=[],
            caveats=[],
            error={
                "code": error_code.value,
                "message": final_message,
                "suggestion": final_suggestion,
            },
            telemetry_id=telemetry_id,
            execution_time_ms=execution_time_ms,
        )

    @staticmethod
    def create_mock_output(
        question: str,
        tenant_id: str,
        success: bool = True,
        rows: List[Dict] = None,
    ) -> SQLToolOutput:
        """
        Create a mock output for testing.

        Args:
            question: User question.
            tenant_id: Tenant ID.
            success: Whether mock succeeded.
            rows: Mock rows to return.

        Returns:
            SQLToolOutput instance.
        """
        import uuid

        return SQLToolOutput(
            success=success,
            sql="SELECT * FROM view LIMIT 100" if success else None,
            rows=rows or [],
            columns=[{"name": "id", "type": "integer"}] if rows else [],
            caveats=["Mock result for testing"],
            error=None if success else {
                "code": SQLToolError.VALIDATION_ERROR.value,
                "message": "Mock validation error",
            },
            telemetry_id=str(uuid.uuid4()),
            execution_time_ms=0.0,
        )


# Tool instance
sql_tool = QueryDatabaseTextToSQL()


def register_sql_tool_with_registry(registry) -> bool:
    """
    Register SQL tool with the provided registry.

    Args:
        registry: ToolRegistry instance.

    Returns:
        True if registration successful.
    """
    try:
        tool_def = QueryDatabaseTextToSQL.get_tool_definition()
        logger.info(f"Registering SQL tool: {tool_def['name']}")
        # Registry integration would happen here
        # For Phase 0, this is a placeholder
        return True
    except Exception as e:
        logger.error(f"Failed to register SQL tool: {e}")
        return False
