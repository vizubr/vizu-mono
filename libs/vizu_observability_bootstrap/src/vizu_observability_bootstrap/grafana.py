"""
Grafana Cloud integration module for Vizu services.

This module provides helpers for Grafana Cloud observability stack:
- OTLP traces/metrics to Grafana Tempo/Mimir
- Structured logging compatible with Grafana Loki
- Health metrics for Grafana dashboards

The main telemetry is handled by OpenTelemetry in __init__.py.
This module adds Grafana-specific helpers and logging formatters.

Usage:
    from vizu_observability_bootstrap.grafana import setup_grafana_logging, create_grafana_logger

    # Set up structured logging for Grafana Loki
    setup_grafana_logging(service_name="atendente_core")
"""
import logging
import os
import json
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def is_grafana_enabled() -> bool:
    """Check if Grafana Cloud OTLP is configured."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    return "grafana.net" in endpoint


class GrafanaLokiFormatter(logging.Formatter):
    """
    JSON formatter optimized for Grafana Loki.
    
    Produces logs in a format that Loki can parse and index efficiently.
    Includes trace correlation fields when available.
    """

    def __init__(self, service_name: str, environment: str = "development"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
            "service": self.service_name,
            "environment": self.environment,
            "source": {
                "file": record.filename,
                "function": record.funcName,
                "line": record.lineno,
            },
        }

        # Add OpenTelemetry trace context if available
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span and span.is_recording():
                ctx = span.get_span_context()
                log_record["trace_id"] = format(ctx.trace_id, '032x')
                log_record["span_id"] = format(ctx.span_id, '016x')
        except ImportError:
            pass

        # Add exception info if present
        if record.exc_info:
            log_record["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack_trace": self.formatException(record.exc_info) if record.exc_info else None,
            }

        # Add any extra fields from the log record
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName"
            ) and not key.startswith("_"):
                try:
                    json.dumps(value)  # Check if serializable
                    log_record[key] = value
                except (TypeError, ValueError):
                    log_record[key] = str(value)

        return json.dumps(log_record, default=str)


def setup_grafana_logging(
    service_name: str,
    environment: Optional[str] = None,
    log_level: str = "INFO",
) -> None:
    """
    Configure structured JSON logging for Grafana Loki.

    Args:
        service_name: Name of the service for log labels
        environment: Environment name (defaults to ENVIRONMENT env var)
        log_level: Logging level (defaults to LOG_LEVEL env var or INFO)
    """
    env = environment or os.environ.get("ENVIRONMENT", "development")
    level = os.environ.get("LOG_LEVEL", log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add Loki-compatible JSON handler
    handler = logging.StreamHandler()
    handler.setFormatter(GrafanaLokiFormatter(service_name, env))
    root_logger.addHandler(handler)

    logger.info(
        "Grafana logging configured",
        extra={"service": service_name, "environment": env, "level": level}
    )


def create_grafana_logger(name: str) -> logging.Logger:
    """
    Create a logger instance configured for Grafana.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def record_metric(
    metric_name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
    metric_type: str = "gauge",
) -> None:
    """
    Record a custom metric via OpenTelemetry (sent to Grafana Mimir).

    Args:
        metric_name: Name of the metric (e.g., "vizu.chat.response_time_ms")
        value: Metric value
        labels: Optional dict of labels
        metric_type: One of "gauge", "counter", "histogram"
    """
    try:
        from opentelemetry import metrics
        
        meter = metrics.get_meter("vizu.custom")
        
        if metric_type == "counter":
            counter = meter.create_counter(metric_name)
            counter.add(value, labels or {})
        elif metric_type == "histogram":
            histogram = meter.create_histogram(metric_name)
            histogram.record(value, labels or {})
        else:  # gauge
            # OpenTelemetry gauges need a callback, so we use UpDownCounter for simple gauges
            gauge = meter.create_up_down_counter(metric_name)
            gauge.add(value, labels or {})
            
    except Exception as e:
        logger.debug(f"Failed to record metric {metric_name}: {e}")


def health_check() -> dict:
    """
    Return Grafana/OTEL integration health status.

    Returns:
        Dict with status information for monitoring endpoints.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    
    status = {
        "grafana_enabled": is_grafana_enabled(),
        "otlp_endpoint": endpoint,
        "otlp_headers_configured": bool(headers),
        "service_name": os.environ.get("OTEL_SERVICE_NAME"),
        "environment": os.environ.get("ENVIRONMENT"),
    }

    # Check if tracer is working
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        status["tracer_available"] = tracer is not None
    except Exception:
        status["tracer_available"] = False

    return status


# Aliases for backward compatibility with datadog module
setup_datadog = setup_grafana_logging  # No-op compatibility
create_datadog_logger = create_grafana_logger
track_custom_metric = record_metric
