"""
Tests for SQL tool registration and execution.
"""

import pytest
from vizu_tool_registry.tools.sql_tool import (
    QueryDatabaseTextToSQL,
    SQLToolInput,
    SQLToolOutput,
    SQLToolError,
    sql_tool,
)


class TestSQLToolInput:
    """Tests for SQLToolInput."""

    def test_input_creation(self):
        """Test basic input creation."""
        input_data = SQLToolInput(
            question="How many customers are there?",
            tenant_id="tenant123",
            role="analyst",
        )
        assert input_data.question == "How many customers are there?"
        assert input_data.tenant_id == "tenant123"
        assert input_data.role == "analyst"

    def test_input_with_constraints(self):
        """Test input with optional constraints."""
        input_data = SQLToolInput(
            question="Top products this month",
            tenant_id="tenant123",
            role="analyst",
            optional_constraints={"date_range": "last_30_days", "max_rows": 50},
        )
        assert input_data.optional_constraints["date_range"] == "last_30_days"
        assert input_data.optional_constraints["max_rows"] == 50

    def test_input_validate_valid(self):
        """Test validation of valid input."""
        input_data = SQLToolInput(
            question="Test question",
            tenant_id="tenant123",
            role="analyst",
        )
        assert input_data.validate() is True

    def test_input_validate_missing_question(self):
        """Test validation fails with missing question."""
        input_data = SQLToolInput(
            question="",
            tenant_id="tenant123",
            role="analyst",
        )
        assert input_data.validate() is False

    def test_input_validate_missing_tenant_id(self):
        """Test validation fails with missing tenant_id."""
        input_data = SQLToolInput(
            question="Test question",
            tenant_id="",
            role="analyst",
        )
        assert input_data.validate() is False

    def test_input_validate_missing_role(self):
        """Test validation fails with missing role."""
        input_data = SQLToolInput(
            question="Test question",
            tenant_id="tenant123",
            role="",
        )
        assert input_data.validate() is False


class TestSQLToolOutput:
    """Tests for SQLToolOutput."""

    def test_output_creation(self):
        """Test basic output creation."""
        output = SQLToolOutput(
            success=True,
            sql="SELECT * FROM customers LIMIT 100",
            rows=[{"id": 1, "name": "Alice"}],
            columns=[{"name": "id", "type": "integer"}],
        )
        assert output.success is True
        assert len(output.rows) == 1

    def test_output_default_values(self):
        """Test output initializes default values."""
        output = SQLToolOutput(success=False)
        assert output.rows == []
        assert output.columns == []
        assert output.caveats == []

    def test_output_to_dict(self):
        """Test conversion to dict."""
        output = SQLToolOutput(
            success=True,
            sql="SELECT COUNT(*)",
            rows=[{"count": 100}],
            columns=[{"name": "count", "type": "integer"}],
            telemetry_id="uuid123",
        )
        d = output.to_dict()
        assert d["success"] is True
        assert d["sql"] == "SELECT COUNT(*)"
        assert len(d["rows"]) == 1
        assert d["telemetry_id"] == "uuid123"

    def test_output_error_case(self):
        """Test output with error."""
        output = SQLToolOutput(
            success=False,
            sql=None,
            rows=[],
            error={
                "code": SQLToolError.VALIDATION_ERROR.value,
                "message": "Query failed validation",
                "suggestion": "Use a different view",
            },
            telemetry_id="uuid456",
        )
        assert output.success is False
        assert output.sql is None
        assert output.error["code"] == "VALIDATION_ERROR"


class TestQueryDatabaseTextToSQL:
    """Tests for QueryDatabaseTextToSQL tool."""

    def test_tool_definition(self):
        """Test tool definition schema."""
        definition = QueryDatabaseTextToSQL.get_tool_definition()
        assert definition["name"] == "query_database_text_to_sql"
        assert "inputSchema" in definition
        assert "outputSchema" in definition
        assert definition["inputSchema"]["properties"]["question"]
        assert definition["inputSchema"]["required"] == ["question", "tenant_id", "role"]

    def test_tool_input_schema_validation(self):
        """Test input schema has correct properties."""
        schema = QueryDatabaseTextToSQL.INPUT_SCHEMA
        assert "question" in schema["properties"]
        assert "tenant_id" in schema["properties"]
        assert "role" in schema["properties"]
        assert schema["properties"]["role"]["enum"] == ["viewer", "analyst", "admin"]

    def test_tool_output_schema(self):
        """Test output schema has correct properties."""
        schema = QueryDatabaseTextToSQL.OUTPUT_SCHEMA
        assert "success" in schema["properties"]
        assert "sql" in schema["properties"]
        assert "rows" in schema["properties"]
        assert "columns" in schema["properties"]
        assert "caveats" in schema["properties"]
        assert "error" in schema["properties"]
        assert "telemetry_id" in schema["properties"]

    def test_tool_invoke_valid_input(self):
        """Test invoking tool with valid input."""
        input_data = SQLToolInput(
            question="How many customers?",
            tenant_id="tenant123",
            role="analyst",
        )
        tool = QueryDatabaseTextToSQL()
        output = tool.invoke(input_data)

        assert output.success is True
        assert output.sql is not None
        assert len(output.rows) > 0
        assert len(output.columns) > 0
        assert output.telemetry_id is not None

    def test_tool_invoke_invalid_input(self):
        """Test invoking tool with invalid input."""
        input_data = SQLToolInput(
            question="",  # Invalid: empty question
            tenant_id="tenant123",
            role="analyst",
        )
        tool = QueryDatabaseTextToSQL()
        output = tool.invoke(input_data)

        assert output.success is False
        assert output.sql is None
        assert output.error is not None
        assert output.error["code"] == SQLToolError.PARSING_ERROR.value

    def test_tool_invoke_returns_telemetry_id(self):
        """Test that invocation returns unique telemetry IDs."""
        tool = QueryDatabaseTextToSQL()
        input_data = SQLToolInput(
            question="Test",
            tenant_id="tenant123",
            role="analyst",
        )

        output1 = tool.invoke(input_data)
        output2 = tool.invoke(input_data)

        # Both should have telemetry IDs
        assert output1.telemetry_id is not None
        assert output2.telemetry_id is not None
        # They should be different
        assert output1.telemetry_id != output2.telemetry_id

    def test_create_mock_output(self):
        """Test creating mock output."""
        mock_output = QueryDatabaseTextToSQL.create_mock_output(
            question="Test",
            tenant_id="tenant123",
            success=True,
            rows=[{"value": 42}],
        )
        assert mock_output.success is True
        assert len(mock_output.rows) == 1
        assert mock_output.rows[0]["value"] == 42

    def test_create_mock_output_failure(self):
        """Test creating mock failure output."""
        mock_output = QueryDatabaseTextToSQL.create_mock_output(
            question="Test",
            tenant_id="tenant123",
            success=False,
        )
        assert mock_output.success is False
        assert mock_output.sql is None
        assert mock_output.error is not None

    def test_sql_tool_singleton(self):
        """Test sql_tool is instance of tool class."""
        assert isinstance(sql_tool, QueryDatabaseTextToSQL)

    def test_tool_invoke_stub_caveat(self):
        """Test stub implementation includes caveats."""
        tool = QueryDatabaseTextToSQL()
        input_data = SQLToolInput(
            question="Test",
            tenant_id="tenant123",
            role="analyst",
        )
        output = tool.invoke(input_data)

        # Stub should include informative caveats
        assert len(output.caveats) > 0
        assert any("limit" in caveat.lower() for caveat in output.caveats)


class TestSQLToolErrorEnum:
    """Tests for SQLToolError enum."""

    def test_error_code_values(self):
        """Test error code values are strings."""
        assert SQLToolError.PARSING_ERROR.value == "PARSING_ERROR"
        assert SQLToolError.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert SQLToolError.EXECUTION_ERROR.value == "EXECUTION_ERROR"
        assert SQLToolError.AUTHORIZATION_ERROR.value == "AUTHORIZATION_ERROR"

    def test_error_code_in_schema(self):
        """Test all error codes are in schema enum."""
        schema = QueryDatabaseTextToSQL.OUTPUT_SCHEMA
        error_schema = schema["properties"]["error"]["properties"]["code"]
        schema_enums = error_schema["enum"]

        for error_code in SQLToolError:
            assert error_code.value in schema_enums
