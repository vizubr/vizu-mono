import logging
import os
from fastapi import FastAPI

from opentelemetry import trace
# 1. IMPORTAÇÃO ATUALIZADA para o OTLP Exporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .logger import setup_structured_logging

# Export health check utilities
from .health import (
    create_health_router,
    check_database_url,
    check_redis_url,
    check_qdrant_url,
    check_http_endpoint,
)

# Export Datadog integration (lazy import to avoid dependency if not used)
def setup_datadog(service_name: str, **kwargs):
    """Initialize Datadog APM. See datadog.py for full docs."""
    from .datadog import setup_datadog as _setup_datadog
    return _setup_datadog(service_name, **kwargs)

__all__ = [
    "setup_telemetry",
    "setup_structured_logging",
    "setup_datadog",
    "create_health_router",
    "check_database_url",
    "check_redis_url",
    "check_qdrant_url",
    "check_http_endpoint",
]

logger = logging.getLogger(__name__)

def setup_telemetry(app: FastAPI, service_name: str):
    resource = Resource(attributes={"service.name": service_name})
    tracer_provider = TracerProvider(resource=resource)

    # 2. CONFIGURAÇÃO ATUALIZADA para usar o OTLP Exporter
    # Por padrão, ele tentará se conectar a um coletor em http://localhost:4317
    # Podemos sobrescrever isso com variáveis de ambiente se necessário.
    exporter = OTLPSpanExporter()

    processor = BatchSpanProcessor(exporter)
    tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app)
    setup_structured_logging()

    logger.info(f"Observabilidade configurada com sucesso para o serviço: {service_name}")
    logger.info(f"OTLP Exporter endpoint: {os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317')}")