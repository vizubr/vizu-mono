"""
Text-to-SQL Validator Exemplar Tests

Tests validator against a corpus of real SQL queries and expected outcomes.
Measures false positive/negative rates.
"""

import pytest
import logging
from typing import List, Dict, Any

from vizu_sql_factory import SqlValidator

logger = logging.getLogger(__name__)


# Exemplar corpus: (sql, should_pass, reason, allowed_views, allowed_columns)
EXEMPLARS = [
    # Valid queries that should PASS
    {
        "sql": "SELECT id, name FROM customers WHERE client_id = '123' LIMIT 100",
        "should_pass": True,
        "reason": "Valid query with tenant filter and limit",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "name", "client_id"]},
    },
    {
        "sql": "SELECT COUNT(*) AS total FROM orders WHERE client_id = '123' LIMIT 10",
        "should_pass": True,
        "reason": "Valid aggregation with tenant filter",
        "allowed_views": ["orders"],
        "allowed_columns": {"orders": ["COUNT", "client_id"]},
    },
    {
        "sql": "SELECT product_id, SUM(amount) FROM transactions WHERE client_id = '123' GROUP BY product_id LIMIT 50",
        "should_pass": True,
        "reason": "Valid GROUP BY with aggregate",
        "allowed_views": ["transactions"],
        "allowed_columns": {"transactions": ["product_id", "amount", "client_id"]},
    },
    {
        "sql": "SELECT a.id, b.name FROM customers a JOIN orders b ON a.id = b.customer_id WHERE a.client_id = '123' LIMIT 100",
        "should_pass": True,
        "reason": "Valid JOIN with tenant filter",
        "allowed_views": ["customers", "orders"],
        "allowed_columns": {"customers": ["id", "client_id"], "orders": ["name", "customer_id"]},
    },
    {
        "sql": "SELECT id FROM users WHERE client_id = '123' AND status = 'active' LIMIT 100",
        "should_pass": True,
        "reason": "Valid query with multiple WHERE conditions",
        "allowed_views": ["users"],
        "allowed_columns": {"users": ["id", "status", "client_id"]},
    },

    # Invalid queries that should FAIL
    {
        "sql": "SELECT * FROM customers WHERE client_id = '123'",
        "should_pass": False,
        "reason": "SELECT * not allowed (not explicit)",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "name"]},
    },
    {
        "sql": "SELECT id, name FROM customers WHERE client_id = '123'",
        "should_pass": False,
        "reason": "No LIMIT clause",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "name", "client_id"]},
    },
    {
        "sql": "SELECT id FROM customers LIMIT 100",
        "should_pass": False,
        "reason": "Missing tenant filter (client_id)",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "client_id"]},
    },
    {
        "sql": "INSERT INTO customers (name) VALUES ('Alice')",
        "should_pass": False,
        "reason": "DDL/DML not allowed (INSERT)",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "name"]},
    },
    {
        "sql": "SELECT id FROM unauthorized_table WHERE client_id = '123' LIMIT 100",
        "should_pass": False,
        "reason": "Table not in allowed_views",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "client_id"]},
    },
    {
        "sql": "SELECT id, secret_column FROM customers WHERE client_id = '123' LIMIT 100",
        "should_pass": False,
        "reason": "Column not in allowlist",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "client_id"]},
    },
    {
        "sql": "SELECT id FROM customers WHERE client_id = '123' LIMIT 10000",
        "should_pass": False,
        "reason": "LIMIT exceeds max_rows (default 100)",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "client_id"]},
    },
    {
        "sql": "DELETE FROM customers WHERE client_id = '123'",
        "should_pass": False,
        "reason": "DDL/DML not allowed (DELETE)",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "client_id"]},
    },
    {
        "sql": "SELECT DANGEROUS_FUNCTION(id) FROM customers WHERE client_id = '123' LIMIT 100",
        "should_pass": False,
        "reason": "Complex function in SELECT (not COUNT/SUM/etc)",
        "allowed_views": ["customers"],
        "allowed_columns": {"customers": ["id", "client_id"]},
    },
]


class TestSqlValidatorExemplars:
    """Test validator against exemplar corpus."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SqlValidator()

    @pytest.mark.parametrize("exemplar", EXEMPLARS)
    def test_exemplar(self, exemplar: Dict[str, Any]):
        """Test single exemplar."""
        sql = exemplar["sql"]
        should_pass = exemplar["should_pass"]
        reason = exemplar["reason"]
        allowed_views = exemplar.get("allowed_views", [])
        allowed_columns = exemplar.get("allowed_columns", {})

        result = self.validator.validate(
            sql=sql,
            tenant_id="123",
            allowed_views=allowed_views,
            allowed_columns=allowed_columns,
            max_rows=100,
            mandatory_filters=["client_id"],
            allow_rewrites=False
        )

        is_valid = result.get("is_valid", False)

        if should_pass:
            assert is_valid, f"Expected PASS but got FAIL: {reason}\nErrors: {result.get('errors')}"
        else:
            assert not is_valid, f"Expected FAIL but got PASS: {reason}"

    def test_exemplar_coverage(self):
        """Verify exemplar coverage."""
        pass_count = sum(1 for e in EXEMPLARS if e["should_pass"])
        fail_count = sum(1 for e in EXEMPLARS if not e["should_pass"])

        logger.info(f"Exemplar corpus: {len(EXEMPLARS)} total, {pass_count} pass, {fail_count} fail")

        assert pass_count >= 5, "Need at least 5 passing exemplars"
        assert fail_count >= 8, "Need at least 8 failing exemplars"

    def test_false_positive_rate(self):
        """Measure false positive rate (PASS when should FAIL)."""
        false_positives = []

        for exemplar in EXEMPLARS:
            if not exemplar["should_pass"]:  # Should be invalid
                result = self.validator.validate(
                    sql=exemplar["sql"],
                    tenant_id="123",
                    allowed_views=exemplar.get("allowed_views", []),
                    allowed_columns=exemplar.get("allowed_columns", {}),
                    max_rows=100,
                    mandatory_filters=["client_id"],
                    allow_rewrites=False
                )

                if result.get("is_valid"):  # But we said it's valid (FALSE POSITIVE)
                    false_positives.append({
                        "sql": exemplar["sql"],
                        "reason": exemplar["reason"],
                        "result": result
                    })

        fp_rate = len(false_positives) / len([e for e in EXEMPLARS if not e["should_pass"]]) * 100
        logger.info(f"False Positive Rate: {fp_rate:.1f}% ({len(false_positives)} FPs)")

        # Fail if FP rate > 10%
        assert fp_rate < 10, f"False positive rate too high: {fp_rate:.1f}%\nFPs: {false_positives}"

    def test_false_negative_rate(self):
        """Measure false negative rate (FAIL when should PASS)."""
        false_negatives = []

        for exemplar in EXEMPLARS:
            if exemplar["should_pass"]:  # Should be valid
                result = self.validator.validate(
                    sql=exemplar["sql"],
                    tenant_id="123",
                    allowed_views=exemplar.get("allowed_views", []),
                    allowed_columns=exemplar.get("allowed_columns", {}),
                    max_rows=100,
                    mandatory_filters=["client_id"],
                    allow_rewrites=False
                )

                if not result.get("is_valid"):  # But we said it's invalid (FALSE NEGATIVE)
                    false_negatives.append({
                        "sql": exemplar["sql"],
                        "reason": exemplar["reason"],
                        "errors": result.get("errors")
                    })

        fn_rate = len(false_negatives) / len([e for e in EXEMPLARS if e["should_pass"]]) * 100
        logger.info(f"False Negative Rate: {fn_rate:.1f}% ({len(false_negatives)} FNs)")

        # Fail if FN rate > 10%
        assert fn_rate < 10, f"False negative rate too high: {fn_rate:.1f}%\nFNs: {false_negatives}"

    def test_accuracy(self):
        """Measure overall accuracy."""
        correct = 0
        total = len(EXEMPLARS)

        for exemplar in EXEMPLARS:
            result = self.validator.validate(
                sql=exemplar["sql"],
                tenant_id="123",
                allowed_views=exemplar.get("allowed_views", []),
                allowed_columns=exemplar.get("allowed_columns", {}),
                max_rows=100,
                mandatory_filters=["client_id"],
                allow_rewrites=False
            )

            is_valid = result.get("is_valid", False)
            should_pass = exemplar["should_pass"]

            if is_valid == should_pass:
                correct += 1

        accuracy = correct / total * 100
        logger.info(f"Validator Accuracy: {accuracy:.1f}% ({correct}/{total})")

        # Fail if accuracy < 90%
        assert accuracy >= 90, f"Validator accuracy too low: {accuracy:.1f}%"


class TestSqlValidatorExemplarEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SqlValidator()

    def test_case_insensitive_keywords(self):
        """Test that validator handles case-insensitive SQL keywords."""
        sqls = [
            "select id from customers where client_id = '123' limit 100",
            "SELECT ID FROM CUSTOMERS WHERE CLIENT_ID = '123' LIMIT 100",
            "Select id From customers Where client_id = '123' Limit 100",
        ]

        for sql in sqls:
            result = self.validator.validate(
                sql=sql,
                tenant_id="123",
                allowed_views=["customers"],
                allowed_columns={"customers": ["id", "client_id"]},
                max_rows=100,
                mandatory_filters=["client_id"]
            )

            assert result.get("is_valid"), f"Failed to handle case variation: {sql}"

    def test_query_with_whitespace_variations(self):
        """Test that validator handles whitespace variations."""
        sqls = [
            "SELECT id FROM customers WHERE client_id = '123' LIMIT 100",
            "SELECT  id  FROM  customers  WHERE  client_id  =  '123'  LIMIT  100",
            "SELECT id\nFROM customers\nWHERE client_id = '123'\nLIMIT 100",
        ]

        for sql in sqls:
            result = self.validator.validate(
                sql=sql,
                tenant_id="123",
                allowed_views=["customers"],
                allowed_columns={"customers": ["id", "client_id"]},
                max_rows=100,
                mandatory_filters=["client_id"]
            )

            assert result.get("is_valid"), f"Failed to handle whitespace: {sql}"

    def test_boundary_limit_values(self):
        """Test LIMIT boundary conditions."""
        # Exactly at max
        result = self.validator.validate(
            sql="SELECT id FROM customers WHERE client_id = '123' LIMIT 100",
            tenant_id="123",
            allowed_views=["customers"],
            allowed_columns={"customers": ["id", "client_id"]},
            max_rows=100
        )
        assert result.get("is_valid"), "Should pass with LIMIT = max_rows"

        # Just over max
        result = self.validator.validate(
            sql="SELECT id FROM customers WHERE client_id = '123' LIMIT 101",
            tenant_id="123",
            allowed_views=["customers"],
            allowed_columns={"customers": ["id", "client_id"]},
            max_rows=100
        )
        assert not result.get("is_valid"), "Should fail with LIMIT > max_rows"
