"""
Tests for ExemplarValidator

Tests the validation harness for:
- Loading exemplars from JSON
- Syntax validation (basic heuristics for Phase 1, full parsing in Phase 2)
- Semantic matching against regex patterns
- Hallucination detection (disallowed views, tables, aggregates)
- Metrics calculation (pass rate, hallucination rate, latency)
- Report generation
"""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import asdict

from vizu_sql_factory.exemplar_validator import (
    ExemplarValidator,
    ExemplarStatus,
    ExemplarTestResult,
    ExemplarTestSummary,
    get_validator,
)


class TestExemplarTestResult:
    """Tests for ExemplarTestResult dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ExemplarTestResult(
            exemplar_id="exemplar_001",
            status=ExemplarStatus.PASS,
            question="How many customers?",
            expected_pattern="COUNT",
            generated_sql="SELECT COUNT(*) FROM customers",
            is_semantic_match=True,
            is_syntax_valid=True,
            latency_ms=125.5,
            token_usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        )

        result_dict = result.to_dict()

        assert result_dict["exemplar_id"] == "exemplar_001"
        assert result_dict["status"] == "pass"
        assert result_dict["is_semantic_match"] is True
        assert result_dict["latency_ms"] == 125.5
        assert result_dict["token_usage"]["total_tokens"] == 70


class TestExemplarTestSummary:
    """Tests for ExemplarTestSummary dataclass."""

    def test_pass_rate_calculation(self):
        """Test pass rate percentage calculation."""
        summary = ExemplarTestSummary(
            total_tests=10,
            passed=8,
            failed=2,
        )

        assert summary.pass_rate == 80.0

    def test_pass_rate_zero_tests(self):
        """Test pass rate with zero tests."""
        summary = ExemplarTestSummary(total_tests=0)

        assert summary.pass_rate == 0.0

    def test_hallucination_rate_calculation(self):
        """Test hallucination rate percentage calculation."""
        summary = ExemplarTestSummary(
            total_tests=100,
            hallucination_count=5,
        )

        assert summary.hallucination_rate == 5.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        summary = ExemplarTestSummary(
            total_tests=10,
            passed=9,
            failed=1,
            errors=0,
            hallucination_count=0,
            average_latency_ms=150.0,
            average_tokens=75,
        )

        summary_dict = summary.to_dict()

        assert summary_dict["total_tests"] == 10
        assert summary_dict["passed"] == 9
        assert summary_dict["pass_rate_percent"] == 90.0
        assert summary_dict["hallucination_rate_percent"] == 0.0


class TestExemplarValidatorLoading:
    """Tests for exemplar loading functionality."""

    def test_load_exemplars_success(self, tmp_path):
        """Test successful loading of exemplars from file."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_data = [
            {
                "id": "exemplar_001",
                "category": "basic_count",
                "question": "How many customers?",
                "expected_sql_pattern": "COUNT",
            }
        ]

        exemplars_file.write_text(json.dumps(exemplars_data))

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        assert len(validator.exemplars) == 1
        assert validator.exemplars[0]["id"] == "exemplar_001"

    def test_load_exemplars_file_not_found(self):
        """Test handling when exemplars file doesn't exist."""
        nonexistent_path = Path("/nonexistent/exemplars.json")

        validator = ExemplarValidator(exemplars_path=nonexistent_path)

        assert validator.exemplars == []

    def test_load_exemplars_invalid_json(self, tmp_path):
        """Test handling of invalid JSON."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_file.write_text("invalid json {")

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        assert validator.exemplars == []


class TestSyntaxValidation:
    """Tests for SQL syntax validation."""

    def test_valid_simple_select(self):
        """Test validation of simple SELECT statement."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT COUNT(*) FROM customers WHERE client_id = '123'"

        assert validator._is_sql_syntax_valid(sql) is True

    def test_invalid_no_select(self):
        """Test rejection of non-SELECT statements."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "DELETE FROM customers WHERE id = '123'"

        assert validator._is_sql_syntax_valid(sql) is False

    def test_invalid_no_from_clause(self):
        """Test rejection of SELECT without FROM."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT COUNT(*)"

        assert validator._is_sql_syntax_valid(sql) is False

    def test_invalid_unbalanced_parentheses(self):
        """Test rejection of unbalanced parentheses."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT COUNT( FROM customers"

        assert validator._is_sql_syntax_valid(sql) is False

    def test_invalid_unbalanced_quotes(self):
        """Test rejection of unbalanced quotes."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT * FROM customers WHERE name = 'john"

        assert validator._is_sql_syntax_valid(sql) is False

    def test_empty_sql(self):
        """Test rejection of empty SQL."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        assert validator._is_sql_syntax_valid("") is False
        assert validator._is_sql_syntax_valid("   ") is False


class TestSemanticMatching:
    """Tests for semantic pattern matching."""

    def test_pattern_match_simple(self):
        """Test simple pattern matching."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT COUNT(*) FROM customers"
        pattern = "COUNT"

        assert validator._check_semantic_match(sql, pattern) is True

    def test_pattern_match_case_insensitive(self):
        """Test case-insensitive pattern matching."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "select count(*) from customers"
        pattern = "COUNT"

        assert validator._check_semantic_match(sql, pattern) is True

    def test_pattern_no_match(self):
        """Test pattern mismatch."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT * FROM customers"
        pattern = "SUM"

        assert validator._check_semantic_match(sql, pattern) is False

    def test_pattern_regex(self):
        """Test regex pattern matching."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT COUNT(*) FROM customers WHERE id > 100"
        pattern = r"COUNT\(\*\).*WHERE.*id"

        assert validator._check_semantic_match(sql, pattern) is True

    def test_invalid_regex_pattern(self):
        """Test handling of invalid regex."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT COUNT(*) FROM customers"
        pattern = "(?P<invalid"  # Invalid regex

        assert validator._check_semantic_match(sql, pattern) is False


class TestHallucinationDetection:
    """Tests for hallucination detection."""

    def test_disallowed_view_raw_customer_data(self):
        """Test detection of raw_customer_data view."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT * FROM raw_customer_data"

        assert validator._detect_hallucination(sql) is True

    def test_disallowed_view_information_schema(self):
        """Test detection of information_schema."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT * FROM information_schema.tables"

        assert validator._detect_hallucination(sql) is True

    def test_allowed_view(self):
        """Test that allowed views don't trigger hallucination."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT * FROM customers_view"

        assert validator._detect_hallucination(sql) is False

    def test_ddl_drop_detection(self):
        """Test detection of DROP TABLE statement."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "DROP TABLE customers"

        assert validator._detect_hallucination(sql) is True

    def test_dml_delete_detection(self):
        """Test detection of DELETE statement."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "DELETE FROM customers WHERE id = 1"

        assert validator._detect_hallucination(sql) is True

    def test_sql_injection_union_detection(self):
        """Test detection of UNION-based SQL injection."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT * FROM customers UNION SELECT * FROM admin_users"

        assert validator._detect_hallucination(sql) is True

    def test_sql_injection_semicolon_detection(self):
        """Test detection of semicolon-based injection."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT * FROM customers; DROP TABLE admin;"

        assert validator._detect_hallucination(sql) is True

    def test_disallowed_aggregate_stddev(self):
        """Test detection of disallowed STDDEV aggregate."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT STDDEV(amount) FROM transactions"

        assert validator._detect_hallucination(sql) is True

    def test_disallowed_aggregate_percentile(self):
        """Test detection of disallowed PERCENTILE aggregate."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY amount) FROM transactions"

        assert validator._detect_hallucination(sql) is True

    def test_safe_aggregate_count(self):
        """Test that COUNT is not flagged as hallucination."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT COUNT(*) FROM customers"

        assert validator._detect_hallucination(sql) is False

    def test_safe_aggregate_sum(self):
        """Test that SUM is not flagged as hallucination."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        sql = "SELECT SUM(amount) FROM transactions"

        assert validator._detect_hallucination(sql) is False


class TestValidateExemplar:
    """Tests for exemplar validation."""

    @pytest.mark.asyncio
    async def test_validate_success_case(self):
        """Test validation of successful exemplar."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        exemplar = {
            "id": "exemplar_001",
            "question": "How many customers?",
            "expected_sql_pattern": "COUNT",
        }

        result = await validator.validate_exemplar(
            exemplar=exemplar,
            generated_sql="SELECT COUNT(*) FROM customers",
            latency_ms=100.0,
            token_usage={"total_tokens": 70},
        )

        assert result.exemplar_id == "exemplar_001"
        assert result.status == ExemplarStatus.PASS
        assert result.is_syntax_valid is True
        assert result.is_semantic_match is True
        assert result.hallucination_detected is False

    @pytest.mark.asyncio
    async def test_validate_error_case_expected_unable(self):
        """Test validation of error case expecting UNABLE."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        exemplar = {
            "id": "exemplar_011",
            "question": "Create a table",
            "expected_response": "UNABLE",
        }

        result = await validator.validate_exemplar(
            exemplar=exemplar,
            generated_sql="UNABLE: Cannot execute DDL statements",
        )

        assert result.status == ExemplarStatus.PASS
        assert result.is_semantic_match is True

    @pytest.mark.asyncio
    async def test_validate_error_case_should_fail(self):
        """Test that incorrect error response fails."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        exemplar = {
            "id": "exemplar_011",
            "question": "Create a table",
            "expected_response": "UNABLE",
        }

        result = await validator.validate_exemplar(
            exemplar=exemplar,
            generated_sql="CREATE TABLE foo (id INT)",  # Wrong: not UNABLE
        )

        assert result.status == ExemplarStatus.FAIL
        assert result.is_semantic_match is False

    @pytest.mark.asyncio
    async def test_validate_hallucination_detection(self):
        """Test that hallucination causes failure."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        exemplar = {
            "id": "exemplar_002",
            "question": "Show top customers",
            "expected_sql_pattern": "SELECT",
        }

        result = await validator.validate_exemplar(
            exemplar=exemplar,
            generated_sql="SELECT * FROM raw_customer_data",  # Disallowed view
        )

        assert result.status == ExemplarStatus.FAIL
        assert result.hallucination_detected is True

    @pytest.mark.asyncio
    async def test_validate_invalid_syntax(self):
        """Test that invalid SQL causes failure."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        exemplar = {
            "id": "exemplar_003",
            "question": "Count records",
            "expected_sql_pattern": "COUNT",
        }

        result = await validator.validate_exemplar(
            exemplar=exemplar,
            generated_sql="SELECT COUNT FROM customers",  # Missing (*)
        )

        assert result.status == ExemplarStatus.FAIL
        assert result.is_syntax_valid is False

    @pytest.mark.asyncio
    async def test_validate_semantic_mismatch(self):
        """Test that semantic mismatch causes failure."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        exemplar = {
            "id": "exemplar_004",
            "question": "Sum amounts",
            "expected_sql_pattern": "SUM",
        }

        result = await validator.validate_exemplar(
            exemplar=exemplar,
            generated_sql="SELECT AVG(amount) FROM transactions",  # Wrong: AVG not SUM
        )

        assert result.status == ExemplarStatus.FAIL
        assert result.is_semantic_match is False


class TestValidateAll:
    """Tests for batch validation."""

    @pytest.mark.asyncio
    async def test_validate_all_success(self, tmp_path):
        """Test batch validation with all passing."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_data = [
            {
                "id": "exemplar_001",
                "question": "How many customers?",
                "expected_sql_pattern": "COUNT",
            },
            {
                "id": "exemplar_002",
                "question": "Sum amounts",
                "expected_sql_pattern": "SUM",
            },
        ]

        exemplars_file.write_text(json.dumps(exemplars_data))

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        # Mock LLM call
        async def mock_llm(question):
            if "How many" in question:
                return ("SELECT COUNT(*) FROM customers", 100.0, {"total_tokens": 70})
            else:
                return ("SELECT SUM(amount) FROM transactions", 120.0, {"total_tokens": 75})

        summary = await validator.validate_all(mock_llm)

        assert summary.total_tests == 2
        assert summary.passed == 2
        assert summary.failed == 0
        assert summary.errors == 0
        assert summary.pass_rate == 100.0

    @pytest.mark.asyncio
    async def test_validate_all_with_failures(self, tmp_path):
        """Test batch validation with some failures."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_data = [
            {
                "id": "exemplar_001",
                "question": "How many customers?",
                "expected_sql_pattern": "COUNT",
            },
            {
                "id": "exemplar_002",
                "question": "Sum amounts",
                "expected_sql_pattern": "SUM",
            },
        ]

        exemplars_file.write_text(json.dumps(exemplars_data))

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        # Mock LLM call (one correct, one hallucinating)
        async def mock_llm(question):
            if "How many" in question:
                return ("SELECT COUNT(*) FROM customers", 100.0, {"total_tokens": 70})
            else:
                # Hallucination: using disallowed view
                return ("SELECT SUM(amount) FROM raw_transactions", 120.0, {"total_tokens": 75})

        summary = await validator.validate_all(mock_llm)

        assert summary.total_tests == 2
        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.hallucination_count == 1
        assert summary.pass_rate == 50.0
        assert summary.hallucination_rate == 50.0

    @pytest.mark.asyncio
    async def test_validate_all_with_errors(self, tmp_path):
        """Test batch validation with LLM errors."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_data = [
            {
                "id": "exemplar_001",
                "question": "How many customers?",
                "expected_sql_pattern": "COUNT",
            },
        ]

        exemplars_file.write_text(json.dumps(exemplars_data))

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        # Mock LLM call that raises
        async def mock_llm(question):
            raise RuntimeError("LLM service unavailable")

        summary = await validator.validate_all(mock_llm)

        assert summary.total_tests == 1
        assert summary.errors == 1

    @pytest.mark.asyncio
    async def test_validate_all_with_filter(self, tmp_path):
        """Test batch validation with exemplar filtering."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_data = [
            {
                "id": "exemplar_001",
                "question": "How many customers?",
                "category": "basic_count",
                "expected_sql_pattern": "COUNT",
            },
            {
                "id": "exemplar_002",
                "question": "Sum amounts",
                "category": "aggregation",
                "expected_sql_pattern": "SUM",
            },
        ]

        exemplars_file.write_text(json.dumps(exemplars_data))

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        # Mock LLM call
        async def mock_llm(question):
            return ("SELECT COUNT(*) FROM customers", 100.0, {"total_tokens": 70})

        # Test only basic_count exemplars
        summary = await validator.validate_all(
            mock_llm,
            exemplars_filter={"category": "basic_count"}
        )

        assert summary.total_tests == 1
        assert len(summary.results) == 1
        assert summary.results[0].exemplar_id == "exemplar_001"

    @pytest.mark.asyncio
    async def test_validate_all_latency_calculation(self, tmp_path):
        """Test average latency calculation."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_data = [
            {
                "id": "exemplar_001",
                "question": "Count?",
                "expected_sql_pattern": "COUNT",
            },
            {
                "id": "exemplar_002",
                "question": "Sum?",
                "expected_sql_pattern": "SUM",
            },
        ]

        exemplars_file.write_text(json.dumps(exemplars_data))

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        # Mock LLM call with specific latencies
        async def mock_llm(question):
            if "Count" in question:
                return ("SELECT COUNT(*) FROM customers", 100.0, {"total_tokens": 70})
            else:
                return ("SELECT SUM(amount) FROM transactions", 150.0, {"total_tokens": 75})

        summary = await validator.validate_all(mock_llm)

        assert summary.average_latency_ms == 125.0  # (100 + 150) / 2

    @pytest.mark.asyncio
    async def test_validate_all_token_calculation(self, tmp_path):
        """Test average token calculation."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_data = [
            {
                "id": "exemplar_001",
                "question": "Count?",
                "expected_sql_pattern": "COUNT",
            },
            {
                "id": "exemplar_002",
                "question": "Sum?",
                "expected_sql_pattern": "SUM",
            },
        ]

        exemplars_file.write_text(json.dumps(exemplars_data))

        validator = ExemplarValidator(exemplars_path=exemplars_file)

        # Mock LLM call with specific token counts
        async def mock_llm(question):
            if "Count" in question:
                return ("SELECT COUNT(*) FROM customers", 100.0, {"total_tokens": 70})
            else:
                return ("SELECT SUM(amount) FROM transactions", 150.0, {"total_tokens": 80})

        summary = await validator.validate_all(mock_llm)

        assert summary.average_tokens == 75  # (70 + 80) / 2


class TestReportGeneration:
    """Tests for report generation."""

    def test_generate_report_success(self, tmp_path):
        """Test generation of success report."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        summary = ExemplarTestSummary(
            total_tests=10,
            passed=9,
            failed=1,
            errors=0,
            skipped=0,
            hallucination_count=0,
            average_latency_ms=125.5,
            average_tokens=75,
        )

        # Add some results
        summary.results = [
            ExemplarTestResult(
                exemplar_id="exemplar_001",
                status=ExemplarStatus.PASS,
                question="How many customers?",
                expected_pattern="COUNT",
                generated_sql="SELECT COUNT(*) FROM customers",
            ),
        ]

        report = validator.generate_report(summary)

        assert "EXEMPLAR VALIDATION REPORT" in report
        assert "Pass Rate: 90.0%" in report
        assert "Hallucinations: 0 (0.0%)" in report
        assert "Passed (1)" in report

    def test_generate_report_with_failures(self):
        """Test generation of report with failures."""
        validator = ExemplarValidator(exemplars_path=Path("/nonexistent"))

        summary = ExemplarTestSummary(
            total_tests=10,
            passed=7,
            failed=3,
            errors=0,
            skipped=0,
            hallucination_count=2,
            average_latency_ms=150.0,
            average_tokens=80,
        )

        summary.results = [
            ExemplarTestResult(
                exemplar_id="exemplar_001",
                status=ExemplarStatus.FAIL,
                question="Show all data",
                expected_pattern="SELECT",
                generated_sql="SELECT * FROM raw_customer_data",
                hallucination_detected=True,
            ),
        ]

        report = validator.generate_report(summary)

        assert "Failed (1)" in report
        assert "Hallucinations: 2" in report
        assert "hallucination" in report.lower()


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_validator_singleton(self):
        """Test that get_validator returns singleton."""
        validator1 = get_validator()
        validator2 = get_validator()

        assert validator1 is validator2

    def test_get_validator_with_path(self, tmp_path):
        """Test that get_validator with path creates new instance."""
        exemplars_file = tmp_path / "exemplars.json"
        exemplars_file.write_text(json.dumps([]))

        # Reset singleton
        import vizu_sql_factory.exemplar_validator as module
        module._validator = None

        validator = get_validator(exemplars_path=exemplars_file)

        assert validator.exemplars_path == exemplars_file
