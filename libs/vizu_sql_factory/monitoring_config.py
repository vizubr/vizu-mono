"""
Monitoring and alerting configuration for text-to-sql tool operations.

Defines:
- Key metrics to monitor
- Alert thresholds and conditions
- Dashboard definitions
- Audit log requirements
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertCondition(Enum):
    """Alert trigger conditions."""
    QUERY_SUCCESS_RATE_LOW = "query_success_rate_low"
    VALIDATION_FAILURE_RATE_HIGH = "validation_failure_rate_high"
    TIMEOUT_RATE_HIGH = "timeout_rate_high"
    RLS_DENIAL_RATE_SPIKE = "rls_denial_rate_spike"
    CROSS_TENANT_LEAKAGE_DETECTED = "cross_tenant_leakage_detected"
    SCHEMA_DRIFT_DETECTED = "schema_drift_detected"
    LLM_HALLUCINATION_RATE_HIGH = "llm_hallucination_rate_high"
    QUERY_LATENCY_HIGH = "query_latency_high"
    ALLOWLIST_MODIFICATION = "allowlist_modification"
    UNAUTHORIZED_TABLE_ACCESS = "unauthorized_table_access"


@dataclass
class AlertRule:
    """Definition of an alert rule."""
    condition: AlertCondition
    severity: AlertSeverity
    threshold: Any
    window_minutes: int
    message_template: str
    action: str  # "notify", "page", "page_escalate"

    def __post_init__(self):
        """Validate rule."""
        if self.window_minutes < 1:
            raise ValueError("window_minutes must be >= 1")


# Define alert rules
ALERT_RULES: List[AlertRule] = [
    AlertRule(
        condition=AlertCondition.QUERY_SUCCESS_RATE_LOW,
        severity=AlertSeverity.CRITICAL,
        threshold={"below": 95},  # Less than 95% success
        window_minutes=5,
        message_template="Query success rate is {rate}% (threshold: 95%)",
        action="page",
    ),
    AlertRule(
        condition=AlertCondition.VALIDATION_FAILURE_RATE_HIGH,
        severity=AlertSeverity.WARNING,
        threshold={"above": 10},  # More than 10% validation failures
        window_minutes=15,
        message_template="Validation failure rate is {rate}% (threshold: 10%)",
        action="notify",
    ),
    AlertRule(
        condition=AlertCondition.TIMEOUT_RATE_HIGH,
        severity=AlertSeverity.WARNING,
        threshold={"above": 5},  # More than 5% timeouts
        window_minutes=10,
        message_template="Query timeout rate is {rate}% (threshold: 5%)",
        action="notify",
    ),
    AlertRule(
        condition=AlertCondition.RLS_DENIAL_RATE_SPIKE,
        severity=AlertSeverity.CRITICAL,
        threshold={"spike": 10},  # 10x increase in RLS denials
        window_minutes=5,
        message_template="RLS denial rate spiked {multiplier}x (was {baseline}%, now {current}%)",
        action="page",
    ),
    AlertRule(
        condition=AlertCondition.CROSS_TENANT_LEAKAGE_DETECTED,
        severity=AlertSeverity.CRITICAL,
        threshold={},
        window_minutes=1,
        message_template="Cross-tenant data leakage detected: {details}",
        action="page_escalate",
    ),
    AlertRule(
        condition=AlertCondition.SCHEMA_DRIFT_DETECTED,
        severity=AlertSeverity.WARNING,
        threshold={},
        window_minutes=60,
        message_template="Schema changes without corresponding allowlist update: {details}",
        action="notify",
    ),
    AlertRule(
        condition=AlertCondition.LLM_HALLUCINATION_RATE_HIGH,
        severity=AlertSeverity.WARNING,
        threshold={"above": 15},  # More than 15% hallucination rate
        window_minutes=30,
        message_template="LLM hallucination rate is {rate}% (queries attempting disallowed tables)",
        action="notify",
    ),
    AlertRule(
        condition=AlertCondition.QUERY_LATENCY_HIGH,
        severity=AlertSeverity.WARNING,
        threshold={"p95": 5000},  # p95 latency > 5 seconds
        window_minutes=15,
        message_template="Query latency high: p95={latency}ms (threshold: 5000ms)",
        action="notify",
    ),
    AlertRule(
        condition=AlertCondition.ALLOWLIST_MODIFICATION,
        severity=AlertSeverity.INFO,
        threshold={},
        window_minutes=0,
        message_template="Allowlist modified: {changes}",
        action="notify",
    ),
    AlertRule(
        condition=AlertCondition.UNAUTHORIZED_TABLE_ACCESS,
        severity=AlertSeverity.CRITICAL,
        threshold={},
        window_minutes=1,
        message_template="Attempted access to unauthorized table: {table} by {role}",
        action="page",
    ),
]


@dataclass
class MonitoringMetric:
    """Definition of a metric to monitor."""
    name: str
    description: str
    unit: str
    aggregation: str  # "sum", "avg", "max", "p50", "p95", "p99"
    dimension: Optional[str] = None  # "view", "role", "tenant", None for global


# Define key metrics
KEY_METRICS: List[MonitoringMetric] = [
    # Query execution metrics
    MonitoringMetric("query_count", "Number of queries executed", "count", "sum"),
    MonitoringMetric("query_success_count", "Number of successful queries", "count", "sum"),
    MonitoringMetric("query_failure_count", "Number of failed queries", "count", "sum"),
    MonitoringMetric("query_success_rate", "Percentage of successful queries", "%", "avg"),
    MonitoringMetric("query_execution_time", "Query execution duration", "ms", "avg", "view"),
    MonitoringMetric("query_execution_time_p95", "Query execution p95 latency", "ms", "p95", "view"),
    MonitoringMetric("query_execution_time_p99", "Query execution p99 latency", "ms", "p99", "view"),

    # Validation metrics
    MonitoringMetric("validation_pass_count", "Number of passed validations", "count", "sum"),
    MonitoringMetric("validation_fail_count", "Number of failed validations", "count", "sum"),
    MonitoringMetric("validation_pass_rate", "Percentage of passed validations", "%", "avg"),
    MonitoringMetric("validation_failure_by_reason", "Validation failures by error type", "count", "sum"),

    # Error metrics
    MonitoringMetric("error_llm_unable", "LLM unable to generate SQL", "count", "sum"),
    MonitoringMetric("error_validation_failed", "Validation failures", "count", "sum"),
    MonitoringMetric("error_rls_denied", "RLS access denials", "count", "sum"),
    MonitoringMetric("error_timeout", "Query timeouts", "count", "sum"),
    MonitoringMetric("error_schema_unavailable", "Schema unavailability errors", "count", "sum"),
    MonitoringMetric("error_internal", "Internal errors", "count", "sum"),

    # RLS metrics
    MonitoringMetric("rls_check_count", "Number of RLS checks performed", "count", "sum"),
    MonitoringMetric("rls_denial_count", "Number of RLS denials", "count", "sum"),
    MonitoringMetric("rls_denial_rate", "Percentage of RLS denials", "%", "avg"),

    # LLM metrics
    MonitoringMetric("llm_query_count", "Number of LLM queries", "count", "sum"),
    MonitoringMetric("llm_tokens_used", "Tokens consumed by LLM", "count", "sum"),
    MonitoringMetric("llm_cost", "Cost of LLM queries", "USD", "sum"),
    MonitoringMetric("llm_hallucination_count", "LLM attempts to access disallowed tables", "count", "sum"),
    MonitoringMetric("llm_hallucination_rate", "Percentage of LLM hallucinations", "%", "avg"),

    # Result metrics
    MonitoringMetric("result_count", "Rows returned by queries", "rows", "avg", "view"),
    MonitoringMetric("result_count_max", "Maximum rows returned", "rows", "max", "view"),
    MonitoringMetric("result_size_bytes", "Size of result sets", "bytes", "avg"),

    # User/Tenant metrics
    MonitoringMetric("queries_per_tenant", "Number of queries per tenant", "count", "sum", "tenant"),
    MonitoringMetric("queries_per_role", "Number of queries per role", "count", "sum", "role"),
    MonitoringMetric("unique_users", "Number of unique users", "count", "sum"),
    MonitoringMetric("unique_tenants", "Number of unique tenants", "count", "sum"),

    # Data isolation metrics
    MonitoringMetric("cross_tenant_access_attempts", "Attempts to access other tenants' data", "count", "sum"),
    MonitoringMetric("cross_tenant_leakage_incidents", "Confirmed cross-tenant data leaks", "count", "sum"),
]


# Dashboard definitions
DASHBOARD_CONFIG = {
    "name": "Text-to-SQL Tool Operations",
    "description": "Monitoring dashboard for text-to-sql query tool",
    "panels": [
        {
            "title": "Query Success Rate",
            "metrics": ["query_success_rate"],
            "threshold": 95,
            "alert_rule": AlertCondition.QUERY_SUCCESS_RATE_LOW.value,
        },
        {
            "title": "Query Latency (p95)",
            "metrics": ["query_execution_time_p95"],
            "dimension": "view",
            "threshold": 5000,
            "alert_rule": AlertCondition.QUERY_LATENCY_HIGH.value,
        },
        {
            "title": "Validation Failure Rate",
            "metrics": ["validation_pass_rate"],
            "threshold": 90,
            "alert_rule": AlertCondition.VALIDATION_FAILURE_RATE_HIGH.value,
        },
        {
            "title": "Error Distribution",
            "metrics": ["error_llm_unable", "error_validation_failed", "error_rls_denied", "error_timeout"],
            "type": "stacked_bar",
        },
        {
            "title": "RLS Denial Rate",
            "metrics": ["rls_denial_rate"],
            "threshold": 1,
            "alert_rule": AlertCondition.RLS_DENIAL_RATE_SPIKE.value,
        },
        {
            "title": "LLM Hallucination Rate",
            "metrics": ["llm_hallucination_rate"],
            "threshold": 15,
            "alert_rule": AlertCondition.LLM_HALLUCINATION_RATE_HIGH.value,
        },
        {
            "title": "Queries by Tenant",
            "metrics": ["queries_per_tenant"],
            "dimension": "tenant",
            "type": "table",
        },
        {
            "title": "Queries by Role",
            "metrics": ["queries_per_role"],
            "dimension": "role",
            "type": "pie",
        },
    ],
}


# Audit logging configuration
AUDIT_LOG_CONFIG = {
    "retention_days": 90,
    "hot_storage_days": 30,
    "fields": [
        "timestamp",
        "query_id",
        "user_id",
        "tenant_id",
        "role",
        "question",
        "sql_query",
        "result_count",
        "execution_time_ms",
        "success",
        "error_code",
        "validation_passed",
        "rls_applied",
        "pii_masked",
        "source_ip",
        "user_agent",
    ],
    "sensitive_fields": [
        "sql_query",  # May contain customer data
        "question",    # May contain sensitive keywords
    ],
    "export_format": "JSON Lines",
    "export_destinations": [
        "s3://compliance-logs/vizu-sql-tool/",
        "gcs://compliance-logs/vizu-sql-tool/",
    ],
}


def get_alert_rule(condition: AlertCondition) -> Optional[AlertRule]:
    """Get alert rule for a condition."""
    for rule in ALERT_RULES:
        if rule.condition == condition:
            return rule
    return None


def get_critical_alerts() -> List[AlertRule]:
    """Get all critical alerts."""
    return [r for r in ALERT_RULES if r.severity == AlertSeverity.CRITICAL]


def get_monitoring_metrics_by_dimension(dimension: Optional[str]) -> List[MonitoringMetric]:
    """Get metrics for a specific dimension."""
    return [m for m in KEY_METRICS if m.dimension == dimension]
