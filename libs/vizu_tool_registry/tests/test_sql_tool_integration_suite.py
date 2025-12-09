"""
Integration tests for the SQL tool.

Tests cover:
- Tool schema validation
- Error code handling
- Tool invocation (success and failure paths)
- Role-based access control
- Query validation
"""

import pytest
import json
from uuid import uuid4
from vizu_tool_registry.tools.sql_tool import (
    QueryDatabaseTextToSQL,
    SQLToolInput,
    SQLToolError,
)


class TestSQLToolSchema:
    """Tests for tool schema validity."""

    def test_sql_tool_schema_valid(self):
        """Tool schema is valid JSON Schema."""
        tool = QueryDatabaseTextToSQL()
        schema = tool.get_tool_definition()

        assert "name" in schema
        assert "description" in schema
        assert "inputSchema" in schema
        assert "outputSchema" in schema

        # Validate input schema structure
        input_schema = schema["inputSchema"]
        assert input_schema["type"] == "object"
        assert "properties" in input_schema
        assert "required" in input_schema
        assert set(input_schema["required"]) == {"question", "tenant_id", "role"}

        # Validate output schema structure
        output_schema = schema["outputSchema"]
        assert output_schema["type"] == "object"
        assert "properties" in output_schema

    def test_sql_tool_error_codes_documented(self):
        """All error codes have defined messages and suggestions."""
        tool = QueryDatabaseTextToSQL()
        error_messages = tool._error_messages

        # Check that all error codes have messages
        expected_codes = [
            SQLToolError.LLM_UNABLE.value,
            SQLToolError.VALIDATION_FAILED.value,
            SQLToolError.RLS_DENIED.value,
            SQLToolError.EXECUTION_TIMEOUT.value,
            SQLToolError.SCHEMA_UNAVAILABLE.value,
            SQLToolError.INTERNAL_ERROR.value,
        ]

        for code in expected_codes:
            assert code in error_messages
            assert "message" in error_messages[code]
            assert "suggestion" in error_messages[code]
            assert error_messages[code]["message"]  # Non-empty
            assert error_messages[code]["suggestion"]  # Non-empty


class TestSQLToolInput:
    """Tests for input validation."""

    def test_valid_input(self):
        """Valid input parameters."""
        input_params = SQLToolInput(
            question="How many orders?",
            tenant_id="tenant-123",
            role="analyst",
        )
        assert input_params.validate()

    def test_invalid_input_missing_question(self):
        """Input missing question."""
        input_params = SQLToolInput(
            question="",
            tenant_id="tenant-123",
            role="analyst",
        )
        assert not input_params.validate()

    def test_invalid_input_missing_tenant_id(self):
        """Input missing tenant_id."""
        input_params = SQLToolInput(
            question="How many orders?",
            tenant_id="",
            role="analyst",
        )
        assert not input_params.validate()

    def test_invalid_input_missing_role(self):
        """Input missing role."""
        input_params = SQLToolInput(
            question="How many orders?",
            tenant_id="tenant-123",
            role="",
        )
        assert not input_params.validate()


class TestSQLToolErrors:
    """Tests for error handling and messages."""

    def test_error_result_llm_unable(self):
        """Error result for LLM unable to generate SQL."""
        tool = QueryDatabaseTextToSQL()
        start_time = __import__("datetime").datetime.now()

        result = tool._error_result(
            telemetry_id=str(uuid4()),
            start_time=start_time,
            error_code=SQLToolError.LLM_UNABLE,
        )

        assert not result.success
        assert result.error is not None
        assert result.error["code"] == SQLToolError.LLM_UNABLE.value
        assert "model was unable" in result.error["message"].lower()
        assert "rephrasing" in result.error["suggestion"].lower()

    def test_error_result_validation_failed(self):
        """Error result for validation failure."""
        tool = QueryDatabaseTextToSQL()
        start_time = __import__("datetime").datetime.now()

        result = tool._error_result(
            telemetry_id=str(uuid4()),
            start_time=start_time,
            error_code=SQLToolError.VALIDATION_FAILED,
            available_views=["customers", "orders", "products"],
        )

        assert not result.success
        assert result.error["code"] == SQLToolError.VALIDATION_FAILED.value
        assert "safety constraints" in result.error["message"].lower()
        assert "customers" in result.error["suggestion"]

    def test_error_result_rls_denied(self):
        """Error result for RLS denial."""
        tool = QueryDatabaseTextToSQL()
        start_time = __import__("datetime").datetime.now()

        result = tool._error_result(
            telemetry_id=str(uuid4()),
            start_time=start_time,
            error_code=SQLToolError.RLS_DENIED,
        )

        assert not result.success
        assert result.error["code"] == SQLToolError.RLS_DENIED.value
        assert "denied" in result.error["message"].lower()
        assert "administrator" in result.error["suggestion"].lower()

    def test_error_result_execution_timeout(self):
        """Error result for query timeout."""
        tool = QueryDatabaseTextToSQL()
        start_time = __import__("datetime").datetime.now()

        result = tool._error_result(
            telemetry_id=str(uuid4()),
            start_time=start_time,
            error_code=SQLToolError.EXECUTION_TIMEOUT,
        )

        assert not result.success
        assert result.error["code"] == SQLToolError.EXECUTION_TIMEOUT.value
        assert "timeout" in result.error["message"].lower()
        assert "date range" in result.error["suggestion"].lower()

    def test_error_result_schema_unavailable(self):
        """Error result for schema unavailability."""
        tool = QueryDatabaseTextToSQL()
        start_time = __import__("datetime").datetime.now()

        result = tool._error_result(
            telemetry_id=str(uuid4()),
            start_time=start_time,
            error_code=SQLToolError.SCHEMA_UNAVAILABLE,
        )

        assert not result.success
        assert result.error["code"] == SQLToolError.SCHEMA_UNAVAILABLE.value
        assert "unavailable" in result.error["message"].lower()

    def test_error_result_internal_error(self):
        """Error result for internal error."""
        tool = QueryDatabaseTextToSQL()
        telemetry_id = str(uuid4())
        start_time = __import__("datetime").datetime.now()

        result = tool._error_result(
            telemetry_id=telemetry_id,
            start_time=start_time,
            error_code=SQLToolError.INTERNAL_ERROR,
        )

        assert not result.success
        assert result.error["code"] == SQLToolError.INTERNAL_ERROR.value
        assert telemetry_id in result.error["suggestion"]


class TestSQLToolInvocation:
    """Tests for tool invocation."""

    def test_tool_invocation_with_mock_output(self):
        """Tool invocation returns structured output."""
        mock_output = QueryDatabaseTextToSQL.create_mock_output(
            question="How many orders?",
            tenant_id="tenant-123",
            success=True,
            rows=[{"count": 42}],
        )

        assert mock_output.success
        assert len(mock_output.rows) == 1
        assert mock_output.rows[0]["count"] == 42
        assert mock_output.telemetry_id is not None
        assert mock_output.execution_time_ms is not None

    def test_tool_output_to_dict(self):
        """Tool output can be serialized to dict."""
        mock_output = QueryDatabaseTextToSQL.create_mock_output(
            question="How many orders?",
            tenant_id="tenant-123",
            success=True,
            rows=[{"count": 42}],
        )

        output_dict = mock_output.to_dict()

        assert isinstance(output_dict, dict)
        assert "success" in output_dict
        assert "sql" in output_dict
        assert "rows" in output_dict
        assert "columns" in output_dict
        assert "caveats" in output_dict
        assert "error" in output_dict
        assert "telemetry_id" in output_dict
        assert "execution_time_ms" in output_dict

        # Verify it's JSON serializable
        json_str = json.dumps(output_dict)
        assert json_str


class TestRoleBasedAccess:
    """Tests for role-based access control."""

    def test_viewer_role_config(self):
        """Viewer role has correct configuration."""
        tool = QueryDatabaseTextToSQL()
        config = tool._get_role_config("viewer")

        assert config["max_rows"] == 100
        assert "customers" in config["allowed_views"]
        assert "orders" in config["allowed_views"]

    def test_analyst_role_config(self):
        """Analyst role has correct configuration."""
        tool = QueryDatabaseTextToSQL()
        config = tool._get_role_config("analyst")

        assert config["max_rows"] == 10000
        assert "transactions" in config["allowed_views"]

    def test_admin_role_config(self):
        """Admin role has correct configuration."""
        tool = QueryDatabaseTextToSQL()
        config = tool._get_role_config("admin")

        assert config["max_rows"] == 100000

    def test_row_limit_enforcement_by_role(self):
        """Row limits are correctly enforced per role."""
        tool = QueryDatabaseTextToSQL()

        assert tool._get_max_rows_by_role("viewer") == 100
        assert tool._get_max_rows_by_role("analyst") == 10000
        assert tool._get_max_rows_by_role("admin") == 100000


class TestToolRegistration:
    """Tests for tool registration."""

    def test_tool_definition_complete(self):
        """Tool definition has all required fields."""
        tool_def = QueryDatabaseTextToSQL.get_tool_definition()

        assert tool_def["name"] == "query_database_text_to_sql"
        assert tool_def["description"]
        assert tool_def["inputSchema"]
        assert tool_def["outputSchema"]

    def test_tool_name_matches_constant(self):
        """Tool name matches NAME constant."""
        assert QueryDatabaseTextToSQL.NAME == "query_database_text_to_sql"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
