"""
SQL Validation Observability

Structured logging and metrics for SQL validation decisions.
"""

import logging
import json
import time
from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ValidationLogEntry:
    """Structured log entry for SQL validation."""

    timestamp: str
    tenant_id: str
    user_id: Optional[str]
    role: Optional[str]
    question_hash: str
    original_sql: str
    normalized_sql: Optional[str]
    validation_result: str  # "PASS" or "FAIL"
    checks_passed: int
    checks_failed: int
    check_details: Dict[str, Any]
    execution_time_ms: float
    error_summary: Optional[str]
    suggestions: Optional[str]

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2)


class SqlValidationObserver:
    """
    Observability for SQL validation pipeline.

    Provides:
    - Structured logging of validation decisions
    - Metrics aggregation
    - Error tracking
    """

    def __init__(self, name: str = "sql_validation"):
        """
        Initialize observer.

        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)
        self.metrics = {
            "total_validations": 0,
            "validations_passed": 0,
            "validations_failed": 0,
            "checks": {}
        }

    def log_validation(
        self,
        tenant_id: str,
        original_sql: str,
        validation_result: Dict[str, Any],
        question_hash: str,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        execution_time_ms: float = 0.0
    ) -> ValidationLogEntry:
        """
        Log a validation decision.

        Args:
            tenant_id: Tenant ID
            original_sql: Original SQL query
            validation_result: ValidationResult dict from SqlValidator
            question_hash: Hash of original question
            user_id: User ID (optional)
            role: User role (optional)
            execution_time_ms: Validation execution time

        Returns:
            ValidationLogEntry
        """
        is_valid = validation_result.get("is_valid", False)
        errors = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])
        checks_passed = validation_result.get("checks_passed", [])
        execution_plan = validation_result.get("execution_plan", "")

        entry = ValidationLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            question_hash=question_hash,
            original_sql=original_sql,
            normalized_sql=validation_result.get("normalized_sql"),
            validation_result="PASS" if is_valid else "FAIL",
            checks_passed=len(checks_passed),
            checks_failed=len(errors),
            check_details={
                "passed": checks_passed,
                "failed": [e.get("code") for e in errors] if isinstance(errors, list) else []
            },
            execution_time_ms=execution_time_ms,
            error_summary="; ".join([e.get("message", "") for e in errors]) if errors else None,
            suggestions="; ".join([e.get("suggestion", "") for e in errors]) if errors else None
        )

        # Log at appropriate level
        if is_valid:
            self.logger.info(f"Validation PASS: tenant={tenant_id}, checks_passed={len(checks_passed)}")
        else:
            self.logger.warning(
                f"Validation FAIL: tenant={tenant_id}, errors={len(errors)}, "
                f"summary={entry.error_summary}"
            )

        # Update metrics
        self._update_metrics(is_valid, checks_passed, errors)

        return entry

    def _update_metrics(self, is_valid: bool, checks_passed: list, errors: list):
        """Update metrics."""
        self.metrics["total_validations"] += 1
        if is_valid:
            self.metrics["validations_passed"] += 1
        else:
            self.metrics["validations_failed"] += 1

        # Track individual check pass/fail
        for check in checks_passed:
            if check not in self.metrics["checks"]:
                self.metrics["checks"][check] = {"passed": 0, "failed": 0}
            self.metrics["checks"][check]["passed"] += 1

        # Track failed checks
        if isinstance(errors, list):
            for error in errors:
                check_code = error.get("code", "unknown") if isinstance(error, dict) else error
                if check_code not in self.metrics["checks"]:
                    self.metrics["checks"][check_code] = {"passed": 0, "failed": 0}
                self.metrics["checks"][check_code]["failed"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics."""
        total = self.metrics["total_validations"]
        passed = self.metrics["validations_passed"]
        failed = self.metrics["validations_failed"]

        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "total_validations": total,
            "validations_passed": passed,
            "validations_failed": failed,
            "pass_rate_percent": pass_rate,
            "checks": self.metrics["checks"]
        }

    def log_metrics(self):
        """Log aggregated metrics."""
        metrics = self.get_metrics()
        self.logger.info(
            f"Validation Metrics: total={metrics['total_validations']}, "
            f"passed={metrics['validations_passed']}, "
            f"failed={metrics['validations_failed']}, "
            f"pass_rate={metrics['pass_rate_percent']:.1f}%"
        )


class ValidationTimer:
    """Context manager for timing validation operations."""

    def __init__(self, name: str = "validation", logger_obj: logging.Logger = None):
        """
        Initialize timer.

        Args:
            name: Operation name
            logger_obj: Logger instance
        """
        self.name = name
        self.logger = logger_obj or logger
        self.start_time = None
        self.elapsed_ms = 0

    def __enter__(self):
        """Start timer."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timer and log."""
        if self.start_time:
            self.elapsed_ms = (time.time() - self.start_time) * 1000
            if exc_type:
                self.logger.error(
                    f"{self.name} failed after {self.elapsed_ms:.1f}ms: {exc_val}"
                )
            else:
                self.logger.debug(f"{self.name} completed in {self.elapsed_ms:.1f}ms")


def log_sql_decision(
    sql: str,
    decision: str,
    reason: str = "",
    logger_obj: logging.Logger = None
):
    """
    Log a SQL decision (useful for rewrites).

    Args:
        sql: SQL query
        decision: Decision (e.g., "REWRITE_LIMIT", "INJECT_TENANT_FILTER")
        reason: Reason for decision
        logger_obj: Logger instance
    """
    log = logger_obj or logger
    log.info(f"SQL Decision [{decision}]: {reason}")
    if len(sql) < 200:
        log.debug(f"  Query: {sql}")
    else:
        log.debug(f"  Query: {sql[:200]}...")
