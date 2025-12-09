"""
Health check endpoints for Vizu services.

Provides standardized health, readiness, and liveness endpoints
compatible with Kubernetes, Cloud Run, and monitoring systems.

Usage:
    from vizu_observability_bootstrap.health import create_health_router

    app = FastAPI()
    app.include_router(create_health_router(
        service_name="atendente_core",
        version="1.0.0",
        checks={
            "database": check_database,
            "redis": check_redis,
        }
    ))
"""
import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    """Health check response model."""
    status: str  # "healthy", "degraded", "unhealthy"
    service: str
    version: str
    environment: str
    timestamp: str
    uptime_seconds: float
    checks: Dict[str, Dict[str, Any]]


class ReadinessStatus(BaseModel):
    """Readiness check response model."""
    ready: bool
    checks: Dict[str, bool]


# Track service start time for uptime calculation
_start_time: float = time.time()


def create_health_router(
    service_name: str,
    version: Optional[str] = None,
    checks: Optional[Dict[str, Callable[[], Coroutine[Any, Any, bool]]]] = None,
    timeout_seconds: float = 5.0,
) -> APIRouter:
    """
    Create a FastAPI router with health check endpoints.

    Args:
        service_name: Name of the service
        version: Service version (defaults to DD_VERSION or COMMIT_SHA env var)
        checks: Dict of check_name -> async check function returning bool
        timeout_seconds: Timeout for each health check

    Returns:
        FastAPI APIRouter with /health, /ready, and /live endpoints
    """
    router = APIRouter(tags=["Health"])
    _checks = checks or {}
    _version = version or os.environ.get("DD_VERSION") or os.environ.get("COMMIT_SHA", "unknown")
    _env = os.environ.get("ENVIRONMENT") or os.environ.get("DD_ENV", "development")

    @router.get("/health", response_model=HealthStatus)
    async def health_check() -> HealthStatus:
        """
        Comprehensive health check endpoint.

        Returns detailed status of the service and all configured checks.
        Used by monitoring systems (Datadog, Prometheus, etc.)
        """
        check_results: Dict[str, Dict[str, Any]] = {}
        overall_status = "healthy"

        for check_name, check_func in _checks.items():
            start = time.time()
            try:
                result = await asyncio.wait_for(
                    check_func(),
                    timeout=timeout_seconds
                )
                duration = time.time() - start
                check_results[check_name] = {
                    "status": "ok" if result else "fail",
                    "duration_ms": round(duration * 1000, 2),
                }
                if not result:
                    overall_status = "degraded"
            except asyncio.TimeoutError:
                check_results[check_name] = {
                    "status": "timeout",
                    "duration_ms": timeout_seconds * 1000,
                }
                overall_status = "degraded"
            except Exception as e:
                check_results[check_name] = {
                    "status": "error",
                    "error": str(e),
                }
                overall_status = "unhealthy"
                logger.error(f"Health check {check_name} failed: {e}")

        return HealthStatus(
            status=overall_status,
            service=service_name,
            version=_version,
            environment=_env,
            timestamp=datetime.utcnow().isoformat() + "Z",
            uptime_seconds=round(time.time() - _start_time, 2),
            checks=check_results,
        )

    @router.get("/ready", response_model=ReadinessStatus)
    async def readiness_check(response: Response) -> ReadinessStatus:
        """
        Readiness probe endpoint.

        Returns 200 if the service is ready to accept traffic.
        Returns 503 if any critical check fails.
        Used by load balancers and orchestrators.
        """
        check_results: Dict[str, bool] = {}
        all_ready = True

        for check_name, check_func in _checks.items():
            try:
                result = await asyncio.wait_for(
                    check_func(),
                    timeout=timeout_seconds
                )
                check_results[check_name] = result
                if not result:
                    all_ready = False
            except Exception:
                check_results[check_name] = False
                all_ready = False

        if not all_ready:
            response.status_code = 503

        return ReadinessStatus(ready=all_ready, checks=check_results)

    @router.get("/live")
    async def liveness_check() -> dict:
        """
        Liveness probe endpoint.

        Returns 200 if the service process is running.
        Does NOT check dependencies - just confirms the process is alive.
        Used by orchestrators to detect hung processes.
        """
        return {"alive": True, "timestamp": datetime.utcnow().isoformat() + "Z"}

    @router.get("/metrics")
    async def metrics_endpoint() -> dict:
        """
        Basic metrics endpoint.

        For more comprehensive metrics, integrate with Prometheus or Datadog.
        """
        return {
            "service": service_name,
            "version": _version,
            "environment": _env,
            "uptime_seconds": round(time.time() - _start_time, 2),
            "python_version": os.sys.version,
        }

    return router


# =============================================================================
# Common health check functions
# =============================================================================

async def check_database_url(database_url: Optional[str] = None) -> bool:
    """
    Check database connectivity.

    Args:
        database_url: Database URL (defaults to DATABASE_URL env var)
    """
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        return False

    try:
        import asyncpg
        conn = await asyncpg.connect(url, timeout=5)
        await conn.execute("SELECT 1")
        await conn.close()
        return True
    except ImportError:
        # Try sync fallback
        try:
            import psycopg2
            conn = psycopg2.connect(url, connect_timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return True
        except Exception:
            return False
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False


async def check_redis_url(redis_url: Optional[str] = None) -> bool:
    """
    Check Redis connectivity.

    Args:
        redis_url: Redis URL (defaults to REDIS_URL env var)
    """
    url = redis_url or os.environ.get("REDIS_URL")
    if not url:
        return False

    try:
        import redis.asyncio as redis
        client = redis.from_url(url, socket_timeout=5)
        await client.ping()
        await client.close()
        return True
    except ImportError:
        try:
            import redis as sync_redis
            client = sync_redis.from_url(url, socket_timeout=5)
            client.ping()
            client.close()
            return True
        except Exception:
            return False
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


async def check_qdrant_url(qdrant_url: Optional[str] = None) -> bool:
    """
    Check Qdrant vector DB connectivity.
    """
    url = qdrant_url or os.environ.get("QDRANT_URL")
    if not url:
        return False

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{url}/healthz")
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        return False


async def check_http_endpoint(url: str, expected_status: int = 200) -> bool:
    """
    Generic HTTP endpoint health check.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            return response.status_code == expected_status
    except Exception as e:
        logger.warning(f"HTTP health check failed for {url}: {e}")
        return False
