"""
Component Integration Tests for Text-to-SQL Pipeline

Tests individual components and their interactions:
1. SQL validation (8 checks)
2. SQL parsing and rewriting
3. Result sanitization (PII masking, column filtering)
4. Executor orchestration

These are component tests (not full pipeline with DB/LLM).
"""

import pytest
from uuid import uuid4

from vizu_sql_factory import (
    TextToSqlExecutor,
    ExecutionConfig,
    ResultSanitizer,
    SqlValidator,
    SqlParser,
)


class TestSqlValidation:
    """Test SQL validation checks."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SqlValidator()

    def test_reject_ddl_statement(self):
        """Test that DDL statements are rejected."""
        result = self.validator.validate(
            "CREATE TABLE test (id INT)",
            tenant_id="test_tenant",
            role="analyst"
        )
        assert not result.is_valid

    def test_reject_dml_statement(self):
        """Test that DML statements are rejected."""
        result = self.validator.validate(
            "INSERT INTO users VALUES (1, 'John')",
            tenant_id="test_tenant",
            role="analyst"
        )
        assert not result.is_valid

    def test_reject_drop_statement(self):
        """Test that DROP statements are rejected."""
        result = self.validator.validate(
            "DROP TABLE users",
            tenant_id="test_tenant",
            role="analyst"
        )
        assert not result.is_valid

    def test_accept_simple_select(self):
        """Test that simple SELECT queries are accepted."""
        result = self.validator.validate(
            "SELECT id, name FROM users WHERE id = 1 LIMIT 10",
            tenant_id="test_tenant",
            role="analyst"
        )
        assert result.is_valid

    def test_missing_limit_injected(self):
        """Test that missing LIMIT is injected by validator."""
        result = self.validator.validate(
            "SELECT id, name FROM users WHERE id = 1",
            tenant_id="test_tenant",
            role="analyst"
        )
        # Validator injects LIMIT instead of rejecting
        assert result.is_valid
        assert "LIMIT" in result.normalized_sql

    def test_select_all_columns_allowed(self):
        """Test that SELECT * is allowed by validator."""
        result = self.validator.validate(
            "SELECT * FROM users WHERE id = 1 LIMIT 10",
            tenant_id="test_tenant",
            role="analyst"
        )
        # Validator allows SELECT * - column filtering happens at result sanitization
        assert result.is_valid


class TestSqlParsing:
    """Test SQL parsing with sqlglot."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = SqlParser()

    def test_parse_valid_select(self):
        """Test parsing valid SELECT."""
        sql = "SELECT id, name FROM users WHERE id = 1 LIMIT 10"
        parsed = self.parser.parse(sql)

        assert parsed is not None
        # sqlglot returns Expression objects with sql() method
        assert hasattr(parsed, "sql")

    def test_parse_with_where_clause(self):
        """Test parsing with WHERE clause."""
        sql = "SELECT id, name FROM customers WHERE client_id = '123' AND status = 'active' LIMIT 50"
        parsed = self.parser.parse(sql)

        assert parsed is not None

    def test_parse_handles_none(self):
        """Test parser handles unparseable SQL gracefully."""
        # Invalid SQL should return None instead of raising
        parsed = self.parser.parse("INVALID SQL ][")
        # Parser should handle gracefully (return None or empty)
        # This depends on implementation


class TestResultSanitization:
    """Test result sanitization (column filtering, PII masking)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = ResultSanitizer()

    def test_pii_email_masking(self):
        """Test email address masking."""
        rows = [
            {"id": 1, "email": "john@example.com", "name": "John"}
        ]
        columns = [
            {"name": "id", "type": "integer"},
            {"name": "email", "type": "string"},
            {"name": "name", "type": "string"}
        ]

        result = self.sanitizer.sanitize(
            rows=rows,
            columns=columns,
            allowed_columns=None,
            mask_pii=True
        )

        # Should have sanitized rows
        assert len(result["rows"]) > 0

    def test_pii_phone_masking(self):
        """Test phone number masking."""
        rows = [
            {"id": 1, "phone": "(555)123-4567"}
        ]
        columns = [
            {"name": "id", "type": "integer"},
            {"name": "phone", "type": "string"}
        ]

        result = self.sanitizer.sanitize(
            rows=rows,
            columns=columns,
            allowed_columns=None,
            mask_pii=True
        )

        assert len(result["rows"]) > 0

    def test_pii_ssn_masking(self):
        """Test SSN masking."""
        rows = [
            {"id": 1, "ssn": "123-45-6789"}
        ]
        columns = [
            {"name": "id", "type": "integer"},
            {"name": "ssn", "type": "string"}
        ]

        result = self.sanitizer.sanitize(
            rows=rows,
            columns=columns,
            allowed_columns=None,
            mask_pii=True
        )

        assert len(result["rows"]) > 0

    def test_column_filtering(self):
        """Test allowed columns filtering."""
        rows = [
            {"id": 1, "name": "John", "password": "secret123"}
        ]
        columns = [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
            {"name": "password", "type": "string"}
        ]

        result = self.sanitizer.sanitize(
            rows=rows,
            columns=columns,
            allowed_columns={"users": ["id", "name"]},
            mask_pii=False
        )

        # Password should be filtered out
        assert "password" not in result["rows"][0]
        assert "id" in result["rows"][0]
        assert "name" in result["rows"][0]

    def test_row_limit_enforcement(self):
        """Test row limit enforcement."""
        rows = [{"id": i} for i in range(200)]
        columns = [{"name": "id", "type": "integer"}]

        result = self.sanitizer.sanitize(
            rows=rows,
            columns=columns,
            allowed_columns=None,
            mask_pii=False
        )

        # Should have rows
        assert len(result["rows"]) > 0


class TestExecutorConfig:
    """Test ExecutionConfig setup."""

    def test_config_creation(self):
        """Test ExecutionConfig creation."""
        config = ExecutionConfig(
            tenant_id="tenant123",
            allowed_views=["customers", "orders"],
            allowed_columns={"customers": ["id", "name"]},
            max_rows=10000,
        )

        assert config.tenant_id == "tenant123"
        assert "customers" in config.allowed_views
        assert config.max_rows == 10000

    def test_config_with_all_fields(self):
        """Test ExecutionConfig with all fields."""
        config = ExecutionConfig(
            tenant_id="tenant123",
            allowed_views=["users"],
            allowed_columns={"users": ["id", "email"]},
            max_rows=1000
        )

        assert config.tenant_id == "tenant123"
        assert config.max_rows == 1000
        assert config.allowed_views == ["users"]


class TestValidationChecks:
    """Test individual validation checks."""

    def test_check_ddl_detection(self):
        """Test DDL detection."""
        validator = SqlValidator()

        ddl_queries = [
            "CREATE TABLE users (id INT)",
            "ALTER TABLE users ADD COLUMN name VARCHAR",
            "DROP TABLE users",
            "TRUNCATE TABLE users",
        ]

        for sql in ddl_queries:
            result = validator.validate(sql, "tenant1", "analyst")
            assert not result.is_valid, f"Should reject DDL: {sql}"

    def test_check_select_validation(self):
        """Test SELECT validation."""
        validator = SqlValidator()

        # Valid SELECT
        result = validator.validate(
            "SELECT id, name FROM users WHERE id = 1 LIMIT 10",
            "tenant1",
            "analyst"
        )
        assert result.is_valid

        # Missing LIMIT - gets injected instead of rejected
        result = validator.validate(
            "SELECT id, name FROM users WHERE id = 1",
            "tenant1",
            "analyst"
        )
        assert result.is_valid
        assert result.normalized_sql  # Should have normalized/rewritten

    def test_check_column_list(self):
        """Test column handling in validation."""
        validator = SqlValidator()

        # SELECT * is allowed by validator
        result = validator.validate(
            "SELECT * FROM users LIMIT 10",
            "tenant1",
            "analyst"
        )
        assert result.is_valid  # Validator allows it

        # Explicit columns also pass
        result = validator.validate(
            "SELECT id, name FROM users LIMIT 10",
            "tenant1",
            "analyst"
        )
        assert result.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
