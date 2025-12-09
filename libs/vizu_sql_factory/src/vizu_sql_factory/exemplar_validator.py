"""
Exemplar Dataset and Validation Harness

Phase 1.4: Validates LLM output against exemplar test cases
- Hallucination detection (LLM using disallowed views)
- Syntax validation (generated SQL is valid PostgreSQL)
- Semantic equivalence (LLM SQL matches expected pattern)
- Coverage tracking (which exemplars pass/fail)
- Performance metrics (latency, token usage)
"""

import logging
import json
import re
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time

logger = logging.getLogger(__name__)


class ExemplarStatus(Enum):
    """Status of exemplar test execution."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class ExemplarTestResult:
    """Result from testing a single exemplar."""
    exemplar_id: str
    status: ExemplarStatus
    question: str
    expected_pattern: Optional[str]
    generated_sql: Optional[str]
    is_semantic_match: bool = False
    is_syntax_valid: bool = False
    hallucination_detected: bool = False
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exemplar_id": self.exemplar_id,
            "status": self.status.value,
            "question": self.question,
            "expected_pattern": self.expected_pattern,
            "generated_sql": self.generated_sql,
            "is_semantic_match": self.is_semantic_match,
            "is_syntax_valid": self.is_syntax_valid,
            "hallucination_detected": self.hallucination_detected,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "token_usage": self.token_usage,
        }


@dataclass
class ExemplarTestSummary:
    """Summary of exemplar test run."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    hallucination_count: int = 0
    average_latency_ms: float = 0.0
    average_tokens: int = 0
    results: List[ExemplarTestResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100.0

    @property
    def hallucination_rate(self) -> float:
        """Calculate hallucination rate."""
        if self.total_tests == 0:
            return 0.0
        return (self.hallucination_count / self.total_tests) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "pass_rate_percent": self.pass_rate,
            "hallucination_count": self.hallucination_count,
            "hallucination_rate_percent": self.hallucination_rate,
            "average_latency_ms": self.average_latency_ms,
            "average_tokens": self.average_tokens,
            "results": [r.to_dict() for r in self.results],
        }


class ExemplarValidator:
    """
    Validates LLM output against exemplar test cases.

    Responsibilities:
    1. Load exemplars from exemplars.json
    2. Execute LLM on each exemplar question
    3. Check syntax validity (PostgreSQL parser)
    4. Check semantic equivalence (regex pattern matching)
    5. Detect hallucinations (disallowed views, tables, etc.)
    6. Track metrics (pass rate, hallucination rate, latency)
    7. Generate test report
    """

    # Well-known disallowed views (from allowlist.json)
    DISALLOWED_VIEWS = {
        "raw_customer_data",
        "raw_transactions",
        "raw_credentials",
        "information_schema",
        "pg_tables",
        "pg_columns",
    }

    # Whitelisted aggregate functions
    ALLOWED_AGGREGATES = {
        "COUNT", "SUM", "AVG", "MIN", "MAX"
    }

    # Patterns indicating security violations
    SECURITY_PATTERNS = {
        r"(?i)(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)",
        r"(?i)(;\s*(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER))",  # SQL injection
        r"(?i)(UNION\s+SELECT.*FROM)",  # UNION-based injection
        r"(?i)(exec|execute|script|javascript)",  # Code injection
    }

    def __init__(self, exemplars_path: Optional[Path] = None):
        """
        Initialize validator.

        Args:
            exemplars_path: Path to exemplars.json. Defaults to standard location.
        """
        if exemplars_path is None:
            exemplars_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "exemplars.json"

        self.exemplars_path = exemplars_path
        self.exemplars: List[Dict[str, Any]] = []
        self._load_exemplars()

    def _load_exemplars(self) -> None:
        """Load exemplars from JSON file."""
        if not self.exemplars_path.exists():
            logger.warning(f"Exemplars file not found: {self.exemplars_path}")
            self.exemplars = []
            return

        try:
            with open(self.exemplars_path, "r") as f:
                self.exemplars = json.load(f)
            logger.info(f"Loaded {len(self.exemplars)} exemplars from {self.exemplars_path}")
        except Exception as e:
            logger.exception(f"Error loading exemplars: {e}")
            self.exemplars = []

    def _is_sql_syntax_valid(self, sql: str) -> bool:
        """
        Check if SQL syntax is valid (basic validation).

        In Phase 2, use sqlparse or pg_parse for full validation.
        For Phase 1, use heuristics.

        Args:
            sql: SQL to validate

        Returns:
            True if syntax looks valid
        """
        if not sql or not sql.strip():
            return False

        # Basic checks
        sql_upper = sql.upper().strip()

        # Must be SELECT
        if not sql_upper.startswith("SELECT"):
            return False

        # Must have FROM
        if " FROM " not in sql_upper:
            return False

        # Check for balanced parentheses
        if sql.count("(") != sql.count(")"):
            return False

        # Check for balanced quotes
        if sql.count("'") % 2 != 0:
            return False

        return True

    def _check_semantic_match(self, sql: str, expected_pattern: str) -> bool:
        """
        Check if SQL matches expected regex pattern.

        Args:
            sql: Generated SQL
            expected_pattern: Regex pattern to match

        Returns:
            True if matches
        """
        try:
            return bool(re.search(expected_pattern, sql, re.IGNORECASE | re.DOTALL))
        except re.error as e:
            logger.warning(f"Invalid regex pattern: {e}")
            return False

    def _detect_hallucination(self, sql: str) -> bool:
        """
        Detect if LLM hallucinated (used disallowed views/tables).

        Args:
            sql: Generated SQL

        Returns:
            True if hallucination detected
        """
        sql_upper = sql.upper()

        # Check for disallowed views
        for disallowed in self.DISALLOWED_VIEWS:
            if disallowed.upper() in sql_upper:
                logger.warning(f"Hallucination detected: used disallowed view '{disallowed}'")
                return True

        # Check for security patterns
        for pattern in self.SECURITY_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                logger.warning(f"Hallucination detected: security pattern matched: {pattern}")
                return True

        # Check for disallowed aggregates (heuristic)
        disallowed_aggs = {
            "STDDEV", "VAR", "PERCENTILE", "RANK", "ROW_NUMBER",
            "STRING_AGG", "ARRAY_AGG"
        }

        for disallowed_agg in disallowed_aggs:
            if disallowed_agg in sql_upper:
                logger.warning(f"Hallucination detected: used disallowed aggregate '{disallowed_agg}'")
                return True

        return False

    async def validate_exemplar(
        self,
        exemplar: Dict[str, Any],
        generated_sql: str,
        latency_ms: float = 0.0,
        token_usage: Optional[Dict[str, int]] = None,
    ) -> ExemplarTestResult:
        """
        Validate a single exemplar against generated SQL.

        Args:
            exemplar: Exemplar definition from exemplars.json
            generated_sql: SQL generated by LLM
            latency_ms: LLM call latency
            token_usage: Token usage from LLM

        Returns:
            ExemplarTestResult with pass/fail status
        """
        start_time = time.time()

        exemplar_id = exemplar.get("id", "unknown")
        question = exemplar.get("question", "")
        expected_pattern = exemplar.get("expected_sql_pattern")
        expected_response = exemplar.get("expected_response")

        logger.info(f"[validator] Validating exemplar: {exemplar_id}")

        try:
            # Check if this is an error case
            if expected_response == "UNABLE":
                # LLM should return UNABLE
                if generated_sql and "UNABLE" in generated_sql.upper():
                    status = ExemplarStatus.PASS
                    is_semantic_match = True
                else:
                    status = ExemplarStatus.FAIL
                    is_semantic_match = False

                return ExemplarTestResult(
                    exemplar_id=exemplar_id,
                    status=status,
                    question=question,
                    expected_pattern=expected_response,
                    generated_sql=generated_sql,
                    is_semantic_match=is_semantic_match,
                    is_syntax_valid=False,
                    hallucination_detected=False,
                    latency_ms=latency_ms,
                    token_usage=token_usage,
                    timestamp=start_time,
                )

            # Check syntax
            is_syntax_valid = self._is_sql_syntax_valid(generated_sql)

            # Check hallucination
            hallucination_detected = self._detect_hallucination(generated_sql)

            # Check semantic match
            is_semantic_match = False
            if expected_pattern:
                is_semantic_match = self._check_semantic_match(generated_sql, expected_pattern)

            # Determine status
            if hallucination_detected:
                status = ExemplarStatus.FAIL
            elif not is_syntax_valid:
                status = ExemplarStatus.FAIL
            elif not is_semantic_match:
                status = ExemplarStatus.FAIL
            else:
                status = ExemplarStatus.PASS

            logger.info(
                f"[validator] Result {exemplar_id}: "
                f"status={status.value}, "
                f"syntax={is_syntax_valid}, "
                f"semantic={is_semantic_match}, "
                f"hallucination={hallucination_detected}"
            )

            return ExemplarTestResult(
                exemplar_id=exemplar_id,
                status=status,
                question=question,
                expected_pattern=expected_pattern,
                generated_sql=generated_sql,
                is_semantic_match=is_semantic_match,
                is_syntax_valid=is_syntax_valid,
                hallucination_detected=hallucination_detected,
                latency_ms=latency_ms,
                token_usage=token_usage,
                timestamp=start_time,
            )

        except Exception as e:
            logger.exception(f"[validator] Error validating {exemplar_id}: {e}")
            return ExemplarTestResult(
                exemplar_id=exemplar_id,
                status=ExemplarStatus.ERROR,
                question=question,
                expected_pattern=expected_pattern,
                generated_sql=generated_sql,
                error_message=str(e),
                latency_ms=latency_ms,
                token_usage=token_usage,
                timestamp=start_time,
            )

    async def validate_all(
        self,
        llm_call_fn,
        exemplars_filter: Optional[Dict[str, str]] = None,
    ) -> ExemplarTestSummary:
        """
        Validate all exemplars against LLM.

        Args:
            llm_call_fn: Async function that takes question and returns (sql, latency, tokens)
            exemplars_filter: Filter exemplars by tag or category (optional)

        Returns:
            ExemplarTestSummary with results
        """
        summary = ExemplarTestSummary()

        # Filter exemplars if specified
        exemplars_to_test = self.exemplars
        if exemplars_filter:
            exemplars_to_test = [
                e for e in self.exemplars
                if any(
                    exemplars_filter.get(key) == e.get(key)
                    for key in exemplars_filter.keys()
                )
            ]

        logger.info(f"[validator] Starting validation of {len(exemplars_to_test)} exemplars")

        summary.total_tests = len(exemplars_to_test)

        # Run validations
        for exemplar in exemplars_to_test:
            try:
                # Call LLM
                question = exemplar.get("question", "")
                sql, latency_ms, token_usage = await llm_call_fn(question)

                # Validate
                result = await self.validate_exemplar(
                    exemplar=exemplar,
                    generated_sql=sql,
                    latency_ms=latency_ms,
                    token_usage=token_usage,
                )

                summary.results.append(result)

                # Update summary
                if result.status == ExemplarStatus.PASS:
                    summary.passed += 1
                elif result.status == ExemplarStatus.FAIL:
                    summary.failed += 1
                elif result.status == ExemplarStatus.ERROR:
                    summary.errors += 1
                elif result.status == ExemplarStatus.SKIP:
                    summary.skipped += 1

                if result.hallucination_detected:
                    summary.hallucination_count += 1

            except Exception as e:
                logger.exception(f"Error testing exemplar {exemplar.get('id')}: {e}")
                summary.errors += 1

        # Calculate averages
        if summary.results:
            latencies = [r.latency_ms for r in summary.results if r.latency_ms > 0]
            if latencies:
                summary.average_latency_ms = sum(latencies) / len(latencies)

            tokens = [
                r.token_usage.get("total_tokens", 0)
                for r in summary.results
                if r.token_usage
            ]
            if tokens:
                summary.average_tokens = int(sum(tokens) / len(tokens))

        logger.info(f"[validator] Validation complete: {summary.pass_rate:.1f}% pass, {summary.hallucination_rate:.1f}% hallucination")

        return summary

    def generate_report(self, summary: ExemplarTestSummary) -> str:
        """
        Generate text report of validation results.

        Args:
            summary: ExemplarTestSummary with results

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("EXEMPLAR VALIDATION REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary stats
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Tests:        {summary.total_tests}")
        report.append(f"Passed:             {summary.passed}")
        report.append(f"Failed:             {summary.failed}")
        report.append(f"Errors:             {summary.errors}")
        report.append(f"Skipped:            {summary.skipped}")
        report.append(f"Pass Rate:          {summary.pass_rate:.1f}%")
        report.append(f"Hallucinations:     {summary.hallucination_count} ({summary.hallucination_rate:.1f}%)")
        report.append(f"Avg Latency:        {summary.average_latency_ms:.1f}ms")
        report.append(f"Avg Tokens:         {summary.average_tokens}")
        report.append("")

        # Details by status
        report.append("RESULTS BY STATUS")
        report.append("-" * 80)

        passed = [r for r in summary.results if r.status == ExemplarStatus.PASS]
        report.append(f"\nPASSED ({len(passed)})")
        for result in passed[:10]:  # Show first 10
            report.append(f"  ✓ {result.exemplar_id}: {result.question[:60]}")
        if len(passed) > 10:
            report.append(f"  ... and {len(passed) - 10} more")

        failed = [r for r in summary.results if r.status == ExemplarStatus.FAIL]
        report.append(f"\nFAILED ({len(failed)})")
        for result in failed[:10]:  # Show first 10
            reason = "hallucination" if result.hallucination_detected else "syntax/semantic mismatch"
            report.append(f"  ✗ {result.exemplar_id}: {reason}")
            if result.generated_sql:
                report.append(f"    SQL: {result.generated_sql[:80]}")
        if len(failed) > 10:
            report.append(f"  ... and {len(failed) - 10} more")

        errors = [r for r in summary.results if r.status == ExemplarStatus.ERROR]
        if errors:
            report.append(f"\nERRORS ({len(errors)})")
            for result in errors[:5]:
                report.append(f"  ⚠ {result.exemplar_id}: {result.error_message}")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)


# Singleton instance
_validator: Optional[ExemplarValidator] = None


def get_validator(exemplars_path: Optional[Path] = None) -> ExemplarValidator:
    """Get validator singleton instance."""
    global _validator

    if _validator is None:
        _validator = ExemplarValidator(exemplars_path=exemplars_path)

    return _validator
