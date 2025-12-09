"""
Unit tests for SQL validator.
"""

import pytest

from vizu_sql_factory.validator import (
    SqlValidator,
    ValidationResult,
    ValidationError,
    ValidationErrorType,
)
from vizu_sql_factory.allowlist import (
    AllowlistConfig,
    RoleConfig,
    TenantConfig,
)


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_creation(self):
        """Test basic validation error creation."""
        err = ValidationError(
            type=ValidationErrorType.DISALLOWED_VIEW,
            message="View not allowed",
            severity="error",
            suggestion="Use allowed view instead",
        )
        assert err.type == ValidationErrorType.DISALLOWED_VIEW
        assert err.message == "View not allowed"
        assert err.severity == "error"

    def test_validation_error_str(self):
        """Test error string representation."""
        err = ValidationError(
            type=ValidationErrorType.DISALLOWED_VIEW,
            message="View not allowed",
        )
        assert "[disallowed_view]" in str(err)
        assert "View not allowed" in str(err)


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_validation_result_valid(self):
        """Test valid validation result."""
        result = ValidationResult(
            is_valid=True,
            original_sql="SELECT * FROM customers",
            checks_passed=["parsing", "views"],
        )
        assert result.is_valid is True
        assert result.has_errors() is False

    def test_validation_result_with_errors(self):
        """Test result with errors."""
        err = ValidationError(
            type=ValidationErrorType.DISALLOWED_VIEW,
            message="View not allowed",
            severity="error",
        )
        result = ValidationResult(
            is_valid=False,
            original_sql="SELECT * FROM admin_view",
            errors=[err],
        )
        assert result.is_valid is False
        assert result.has_errors() is True
        assert len(result.errors) == 1

    def test_validation_result_with_warnings(self):
        """Test result with warnings."""
        result = ValidationResult(
            is_valid=True,
            original_sql="SELECT * FROM customers",
            warnings=["No LIMIT clause"],
        )
        assert result.is_valid is True
        assert result.has_warnings() is True

    def test_validation_result_error_summary(self):
        """Test error summary."""
        err1 = ValidationError(
            type=ValidationErrorType.DISALLOWED_VIEW,
            message="View not allowed",
            severity="error",
        )
        err2 = ValidationError(
            type=ValidationErrorType.DDL_DML_DETECTED,
            message="INSERT detected",
            severity="error",
        )
        result = ValidationResult(
            is_valid=False,
            original_sql="INSERT INTO customers VALUES ()",
            errors=[err1, err2],
        )
        summary = result.error_summary()
        assert "View not allowed" in summary
        assert "INSERT detected" in summary

    def test_validation_result_to_dict(self):
        """Test serialization to dict."""
        err = ValidationError(
            type=ValidationErrorType.DISALLOWED_VIEW,
            message="View not allowed",
            severity="error",
        )
        result = ValidationResult(
            is_valid=False,
            original_sql="SELECT * FROM admin_view",
            errors=[err],
            warnings=["No LIMIT"],
            checks_passed=["parsing"],
        )
        d = result.to_dict()
        assert d["is_valid"] is False
        assert len(d["errors"]) == 1
        assert d["errors"][0]["type"] == "disallowed_view"
        assert len(d["warnings"]) == 1
        assert len(d["checks_passed"]) == 1


class TestSqlValidator:
    """Tests for SqlValidator."""

    @pytest.fixture
    def validator_no_allowlist(self):
        """Create validator without allowlist."""
        return SqlValidator()

    @pytest.fixture
    def validator_with_allowlist(self):
        """Create validator with allowlist."""
        analyst_role = RoleConfig(
            views=["customers_view", "orders_view"],
            columns={},
            aggregates=["COUNT", "SUM", "AVG"],
            max_rows=10000,
        )
        tenant = TenantConfig(
            name="Test Tenant",
            roles={"analyst": analyst_role},
        )
        config = AllowlistConfig(
            version="1.0.0",
            tenants={"tenant1": tenant},
        )
        return SqlValidator(allowlist_config=config)

    def test_validator_initialization(self, validator_no_allowlist):
        """Test validator initialization."""
        assert validator_no_allowlist.max_query_length == 5000

    def test_parse_valid_select(self, validator_no_allowlist):
        """Test parsing valid SELECT query."""
        is_valid, error = validator_no_allowlist.parse("SELECT id, name FROM customers")
        assert is_valid is True
        assert error is None

    def test_parse_empty_query(self, validator_no_allowlist):
        """Test parsing empty query."""
        is_valid, error = validator_no_allowlist.parse("")
        assert is_valid is False
        assert "Empty" in error

    def test_parse_non_select_query(self, validator_no_allowlist):
        """Test parsing non-SELECT query."""
        is_valid, error = validator_no_allowlist.parse("INSERT INTO customers VALUES (1, 'test')")
        assert is_valid is False
        assert "SELECT" in error

    def test_parse_unbalanced_parentheses(self, validator_no_allowlist):
        """Test parsing query with unbalanced parentheses."""
        is_valid, error = validator_no_allowlist.parse("SELECT COUNT(id FROM customers")
        assert is_valid is False
        assert "parentheses" in error

    def test_parse_exceeds_max_length(self, validator_no_allowlist):
        """Test parsing query exceeding max length."""
        validator = SqlValidator(max_query_length=10)
        is_valid, error = validator.parse("SELECT * FROM customers WHERE id = 1")
        assert is_valid is False
        assert "exceeds max length" in error

    def test_validate_simple_select(self, validator_no_allowlist):
        """Test validating simple SELECT."""
        result = validator_no_allowlist.validate(
            "SELECT id, name FROM customers LIMIT 100",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is True
        assert "basic_parsing" in result.checks_passed

    def test_validate_insert_query(self, validator_no_allowlist):
        """Test validation blocks INSERT."""
        result = validator_no_allowlist.validate(
            "INSERT INTO customers VALUES (1, 'test')",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is False
        assert any(e.type == ValidationErrorType.DDL_DML_DETECTED for e in result.errors)

    def test_validate_update_query(self, validator_no_allowlist):
        """Test validation blocks UPDATE."""
        result = validator_no_allowlist.validate(
            "UPDATE customers SET name = 'new' WHERE id = 1",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is False
        assert any(e.type == ValidationErrorType.DDL_DML_DETECTED for e in result.errors)

    def test_validate_delete_query(self, validator_no_allowlist):
        """Test validation blocks DELETE."""
        result = validator_no_allowlist.validate(
            "DELETE FROM customers WHERE id = 1",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is False

    def test_validate_drop_query(self, validator_no_allowlist):
        """Test validation blocks DROP."""
        result = validator_no_allowlist.validate(
            "DROP TABLE customers",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is False

    def test_validate_missing_limit_warning(self, validator_no_allowlist):
        """Test validation warns about missing LIMIT."""
        result = validator_no_allowlist.validate(
            "SELECT * FROM customers",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is True  # Not blocking, just warning
        assert len(result.warnings) > 0
        assert "LIMIT" in result.warnings[0]

    def test_validate_with_limit(self, validator_no_allowlist):
        """Test validation passes with LIMIT."""
        result = validator_no_allowlist.validate(
            "SELECT * FROM customers LIMIT 100",
            tenant_id="tenant1",
            role="analyst",
        )
        assert "limit_present" in result.checks_passed

    def test_validate_disallowed_view(self, validator_with_allowlist):
        """Test validation blocks disallowed view."""
        result = validator_with_allowlist.validate(
            "SELECT * FROM admin_view LIMIT 100",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is False
        assert any(e.type == ValidationErrorType.DISALLOWED_VIEW for e in result.errors)

    def test_validate_allowed_view(self, validator_with_allowlist):
        """Test validation allows allowed view."""
        result = validator_with_allowlist.validate(
            "SELECT * FROM customers_view LIMIT 100",
            tenant_id="tenant1",
            role="analyst",
        )
        assert "allowed_views" in result.checks_passed

    def test_validate_disallowed_aggregate(self, validator_with_allowlist):
        """Test validation blocks disallowed aggregate."""
        result = validator_with_allowlist.validate(
            "SELECT STRING_AGG(name, ',') FROM customers_view LIMIT 100",
            tenant_id="tenant1",
            role="analyst",
        )
        assert result.is_valid is False
        assert any(e.type == ValidationErrorType.DISALLOWED_AGGREGATE for e in result.errors)

    def test_validate_allowed_aggregate(self, validator_with_allowlist):
        """Test validation allows allowed aggregate."""
        result = validator_with_allowlist.validate(
            "SELECT COUNT(*) FROM customers_view LIMIT 100",
            tenant_id="tenant1",
            role="analyst",
        )
        assert "allowed_aggregates" in result.checks_passed

    def test_check_no_ddl_dml_select(self, validator_no_allowlist):
        """Test DDL/DML check on SELECT."""
        is_valid, found = validator_no_allowlist._check_no_ddl_dml(
            "SELECT * FROM customers"
        )
        assert is_valid is True
        assert found is None

    def test_check_no_ddl_dml_insert(self, validator_no_allowlist):
        """Test DDL/DML check on INSERT."""
        is_valid, found = validator_no_allowlist._check_no_ddl_dml(
            "INSERT INTO customers VALUES (1)"
        )
        assert is_valid is False
        assert "INSERT" in found

    def test_check_no_ddl_dml_create(self, validator_no_allowlist):
        """Test DDL/DML check on CREATE."""
        is_valid, found = validator_no_allowlist._check_no_ddl_dml(
            "CREATE TABLE customers (id INT)"
        )
        assert is_valid is False
        assert "CREATE" in found

    def test_check_no_ddl_dml_alter(self, validator_no_allowlist):
        """Test DDL/DML check on ALTER."""
        is_valid, found = validator_no_allowlist._check_no_ddl_dml(
            "ALTER TABLE customers ADD COLUMN email VARCHAR"
        )
        assert is_valid is False

    def test_check_limit_present_with_limit(self, validator_no_allowlist):
        """Test LIMIT check with LIMIT clause."""
        has_limit, value = validator_no_allowlist._check_limit_present(
            "SELECT * FROM customers LIMIT 100"
        )
        assert has_limit is True
        assert value == 100

    def test_check_limit_present_without_limit(self, validator_no_allowlist):
        """Test LIMIT check without LIMIT clause."""
        has_limit, value = validator_no_allowlist._check_limit_present(
            "SELECT * FROM customers"
        )
        assert has_limit is False
        assert value is None

    def test_check_limit_with_offset(self, validator_no_allowlist):
        """Test LIMIT check with LIMIT and OFFSET."""
        has_limit, value = validator_no_allowlist._check_limit_present(
            "SELECT * FROM customers LIMIT 100 OFFSET 10"
        )
        assert has_limit is True
        assert value == 100

    def test_rewrite_inject_limit(self, validator_no_allowlist):
        """Test rewriting to inject LIMIT."""
        original = "SELECT * FROM customers"
        rewritten = validator_no_allowlist._rewrite_inject_limit(original, 50)
        assert "LIMIT 50" in rewritten
        assert rewritten.endswith(";")

    def test_rewrite_inject_limit_already_present(self, validator_no_allowlist):
        """Test that rewrite doesn't double-inject LIMIT."""
        original = "SELECT * FROM customers LIMIT 100"
        result = validator_no_allowlist.rewrite(
            original,
            tenant_id="tenant1",
            role="analyst",
            max_rows=50,
        )
        # Should not add another LIMIT
        assert result.count("LIMIT") == 1

    def test_explain_valid_result(self, validator_no_allowlist):
        """Test explanation of valid result."""
        result = ValidationResult(
            is_valid=True,
            original_sql="SELECT * FROM customers LIMIT 100",
            checks_passed=["basic_parsing", "no_ddl_dml"],
        )
        explanation = validator_no_allowlist.explain(result)
        assert "✅ VALID" in explanation
        assert "Checks Passed" in explanation

    def test_explain_invalid_result(self, validator_no_allowlist):
        """Test explanation of invalid result."""
        err = ValidationError(
            type=ValidationErrorType.DDL_DML_DETECTED,
            message="INSERT detected",
            severity="error",
            suggestion="Use SELECT only",
        )
        result = ValidationResult(
            is_valid=False,
            original_sql="INSERT INTO customers",
            errors=[err],
        )
        explanation = validator_no_allowlist.explain(result)
        assert "❌ INVALID" in explanation
        assert "Errors" in explanation
        assert "INSERT detected" in explanation
        assert "Use SELECT only" in explanation

    def test_validate_metadata(self, validator_no_allowlist):
        """Test validation result includes metadata."""
        result = validator_no_allowlist.validate(
            "SELECT * FROM customers LIMIT 100",
            tenant_id="test_tenant",
            role="analyst",
        )
        assert result.metadata["tenant_id"] == "test_tenant"
        assert result.metadata["role"] == "analyst"
