"""
Datadog integration module for Vizu services.

This module provides Datadog APM, logging, and metrics integration.
It works alongside OpenTelemetry - traces are sent via OTLP to Datadog's
intake endpoint, while this module handles Datadog-specific features like
profiling, runtime metrics, and log correlation.

Usage:
    from vizu_observability_bootstrap.datadog import setup_datadog

    # Call early in app startup, before other telemetry
    setup_datadog(service_name="atendente_core")
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def is_datadog_enabled() -> bool:
    """Check if Datadog integration should be enabled."""
    return bool(os.environ.get("DD_API_KEY")) and os.environ.get("DD_TRACE_ENABLED", "true").lower() == "true"


def setup_datadog(
    service_name: str,
    env: Optional[str] = None,
    version: Optional[str] = None,
) -> bool:
    """
    Initialize Datadog APM and profiling.

    This should be called BEFORE importing any other modules that might
    be instrumented (like FastAPI, requests, etc.) for automatic instrumentation
    to work properly.

    Args:
        service_name: The name of this service (e.g., "atendente_core")
        env: Environment name (defaults to DD_ENV or "development")
        version: Service version (defaults to DD_VERSION or "unknown")

    Returns:
        True if Datadog was initialized, False if skipped (no API key)
    """
    if not is_datadog_enabled():
        logger.info("Datadog integration disabled (DD_API_KEY not set or DD_TRACE_ENABLED=false)")
        return False

    try:
        # Import ddtrace only when needed
        from ddtrace import config, patch_all, tracer
        from ddtrace.profiling import Profiler

        # Set service info
        config.service = service_name
        config.env = env or os.environ.get("DD_ENV", "development")
        config.version = version or os.environ.get("DD_VERSION", "unknown")

        # Enable log injection for correlation
        config.logs_injection = True

        # Patch all supported libraries for automatic instrumentation
        patch_all()

        # Start continuous profiler if enabled
        if os.environ.get("DD_PROFILING_ENABLED", "false").lower() == "true":
            profiler = Profiler()
            profiler.start()
            logger.info(f"Datadog profiler started for {service_name}")

        logger.info(
            f"Datadog APM initialized: service={service_name}, env={config.env}, version={config.version}"
        )
        return True

    except ImportError:
        logger.warning("ddtrace not installed. Run: pip install ddtrace")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Datadog: {e}")
        return False


def create_datadog_logger(name: str) -> logging.Logger:
    """
    Create a logger configured for Datadog log correlation.

    When DD_LOGS_INJECTION is enabled, logs will automatically include
    trace_id and span_id for correlation in Datadog.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    import json
    from datetime import datetime

    class DatadogJsonFormatter(logging.Formatter):
        """JSON formatter with Datadog-compatible fields."""

        def format(self, record: logging.LogRecord) -> str:
            log_record = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "source": f"{record.filename}:{record.funcName}:{record.lineno}",
            }

            # Add trace correlation if available (injected by ddtrace)
            if hasattr(record, "dd.trace_id"):
                log_record["dd.trace_id"] = getattr(record, "dd.trace_id")
            if hasattr(record, "dd.span_id"):
                log_record["dd.span_id"] = getattr(record, "dd.span_id")

            # Add exception info if present
            if record.exc_info:
                log_record["error"] = {
                    "kind": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                }

            # Add any extra fields
            for key, value in record.__dict__.items():
                if key not in (
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName",
                    "message", "dd.trace_id", "dd.span_id"
                ):
                    log_record[key] = value

            return json.dumps(log_record)

    log = logging.getLogger(name)

    # Only add handler if not already configured
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(DatadogJsonFormatter())
        log.addHandler(handler)
        log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    return log


def track_custom_metric(
    metric_name: str,
    value: float,
    tags: Optional[dict] = None,
    metric_type: str = "gauge",
) -> None:
    """
    Send a custom metric to Datadog.

    Args:
        metric_name: Name of the metric (e.g., "vizu.chat.response_time")
        value: Metric value
        tags: Optional dict of tags (e.g., {"service": "atendente_core"})
        metric_type: One of "gauge", "count", "histogram"
    """
    if not is_datadog_enabled():
        return

    try:
        from ddtrace import tracer

        tag_list = [f"{k}:{v}" for k, v in (tags or {}).items()]

        if metric_type == "gauge":
            tracer.current_span().set_metric(metric_name, value)
        elif metric_type == "count":
            # For counts, use DogStatsD if available
            try:
                from datadog import statsd
                statsd.increment(metric_name, value, tags=tag_list)
            except ImportError:
                tracer.current_span().set_metric(metric_name, value)
        elif metric_type == "histogram":
            try:
                from datadog import statsd
                statsd.histogram(metric_name, value, tags=tag_list)
            except ImportError:
                tracer.current_span().set_metric(metric_name, value)

    except Exception as e:
        logger.debug(f"Failed to track metric {metric_name}: {e}")


def health_check() -> dict:
    """
    Return Datadog integration health status.

    Returns:
        Dict with status information for monitoring endpoints.
    """
    status = {
        "datadog_enabled": is_datadog_enabled(),
        "dd_env": os.environ.get("DD_ENV"),
        "dd_service": os.environ.get("DD_SERVICE"),
        "dd_version": os.environ.get("DD_VERSION"),
        "profiling_enabled": os.environ.get("DD_PROFILING_ENABLED", "false").lower() == "true",
        "logs_injection": os.environ.get("DD_LOGS_INJECTION", "false").lower() == "true",
    }

    if is_datadog_enabled():
        try:
            from ddtrace import tracer
            status["tracer_enabled"] = tracer.enabled
            status["tracer_hostname"] = tracer._hostname
        except Exception:
            status["tracer_enabled"] = False

    return status
