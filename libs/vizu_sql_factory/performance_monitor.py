"""
Performance monitoring for SQL queries.

Tracks and analyzes query performance metrics:
- Query execution time
- Result set size
- Resource usage per view
- Slow query identification
"""

import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class PerformanceLevel(Enum):
    """Performance categorization."""
    FAST = "fast"        # < 100ms
    NORMAL = "normal"    # 100ms - 1s
    SLOW = "slow"        # 1s - 10s
    VERY_SLOW = "very_slow"  # > 10s


@dataclass
class QueryMetrics:
    """Metrics for a single query execution."""
    query_id: str
    view_name: str
    execution_time_ms: float
    result_count: int
    column_count: int
    timestamp: str
    user_role: str
    tenant_id: str
    success: bool
    error_code: Optional[str] = None

    def get_performance_level(self) -> PerformanceLevel:
        """Categorize query performance."""
        if self.execution_time_ms < 100:
            return PerformanceLevel.FAST
        elif self.execution_time_ms < 1000:
            return PerformanceLevel.NORMAL
        elif self.execution_time_ms < 10000:
            return PerformanceLevel.SLOW
        else:
            return PerformanceLevel.VERY_SLOW

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ViewMetrics:
    """Aggregated metrics for a view."""
    view_name: str
    total_queries: int
    successful_queries: int
    failed_queries: int
    avg_execution_time_ms: float
    min_execution_time_ms: float
    max_execution_time_ms: float
    p95_execution_time_ms: float
    p99_execution_time_ms: float
    avg_result_count: int
    max_result_count: int
    last_query_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PerformanceMonitor:
    """Monitors and analyzes query performance."""

    def __init__(self, retention_days: int = 7):
        """
        Initialize monitor.

        Args:
            retention_days: How long to retain metrics
        """
        self.retention_days = retention_days
        self.metrics: List[QueryMetrics] = []
        self.start_time = datetime.utcnow()

    def record_query(self, metrics: QueryMetrics):
        """Record a query execution."""
        self.metrics.append(metrics)
        logger.debug(
            f"Recorded query: view={metrics.view_name}, "
            f"time={metrics.execution_time_ms}ms, "
            f"rows={metrics.result_count}"
        )

    def get_slow_queries(
        self,
        threshold_ms: float = 1000,
        limit: int = 10
    ) -> List[QueryMetrics]:
        """
        Get queries exceeding threshold.

        Args:
            threshold_ms: Minimum execution time (default 1 second)
            limit: Maximum results to return

        Returns:
            List of slow queries, sorted by execution time (slowest first)
        """
        slow = [m for m in self.metrics if m.execution_time_ms >= threshold_ms]
        slow.sort(key=lambda m: m.execution_time_ms, reverse=True)
        return slow[:limit]

    def get_view_metrics(self, view_name: str) -> Optional[ViewMetrics]:
        """
        Get aggregated metrics for a view.

        Args:
            view_name: Name of the view

        Returns:
            ViewMetrics or None if no data
        """
        view_metrics = [m for m in self.metrics if m.view_name == view_name]

        if not view_metrics:
            return None

        successful = [m for m in view_metrics if m.success]
        failed = [m for m in view_metrics if not m.success]

        execution_times = [m.execution_time_ms for m in successful]
        execution_times.sort()

        return ViewMetrics(
            view_name=view_name,
            total_queries=len(view_metrics),
            successful_queries=len(successful),
            failed_queries=len(failed),
            avg_execution_time_ms=sum(execution_times) / len(execution_times) if execution_times else 0,
            min_execution_time_ms=min(execution_times) if execution_times else 0,
            max_execution_time_ms=max(execution_times) if execution_times else 0,
            p95_execution_time_ms=self._percentile(execution_times, 95),
            p99_execution_time_ms=self._percentile(execution_times, 99),
            avg_result_count=sum(m.result_count for m in successful) / len(successful) if successful else 0,
            max_result_count=max((m.result_count for m in successful), default=0),
            last_query_timestamp=max((m.timestamp for m in view_metrics), default=""),
        )

    def get_all_views_metrics(self) -> Dict[str, ViewMetrics]:
        """Get aggregated metrics for all views."""
        views = set(m.view_name for m in self.metrics)
        return {
            view: metrics
            for view in views
            if (metrics := self.get_view_metrics(view)) is not None
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary."""
        if not self.metrics:
            return {
                "total_queries": 0,
                "success_rate": 0,
                "avg_execution_time_ms": 0,
            }

        successful = [m for m in self.metrics if m.success]
        execution_times = [m.execution_time_ms for m in successful]

        performance_counts = defaultdict(int)
        for metrics in successful:
            level = metrics.get_performance_level()
            performance_counts[level.value] += 1

        return {
            "total_queries": len(self.metrics),
            "successful_queries": len(successful),
            "failed_queries": len(self.metrics) - len(successful),
            "success_rate": len(successful) / len(self.metrics) * 100 if self.metrics else 0,
            "avg_execution_time_ms": sum(execution_times) / len(execution_times) if execution_times else 0,
            "min_execution_time_ms": min(execution_times) if execution_times else 0,
            "max_execution_time_ms": max(execution_times) if execution_times else 0,
            "p50_execution_time_ms": self._percentile(execution_times, 50),
            "p95_execution_time_ms": self._percentile(execution_times, 95),
            "p99_execution_time_ms": self._percentile(execution_times, 99),
            "performance_distribution": dict(performance_counts),
        }

    def get_failure_analysis(self) -> Dict[str, Any]:
        """Analyze query failures."""
        failed_metrics = [m for m in self.metrics if not m.success]

        error_counts = defaultdict(int)
        for metrics in failed_metrics:
            if metrics.error_code:
                error_counts[metrics.error_code] += 1

        role_failure_rates = defaultdict(lambda: {"total": 0, "failed": 0})
        for metrics in self.metrics:
            role_failure_rates[metrics.user_role]["total"] += 1
            if not metrics.success:
                role_failure_rates[metrics.user_role]["failed"] += 1

        return {
            "total_failed": len(failed_metrics),
            "failure_rate": len(failed_metrics) / len(self.metrics) * 100 if self.metrics else 0,
            "errors_by_code": dict(error_counts),
            "failure_rate_by_role": {
                role: (counts["failed"] / counts["total"] * 100 if counts["total"] > 0 else 0)
                for role, counts in role_failure_rates.items()
            },
        }

    def recommend_indices(self, view_name: str) -> List[str]:
        """
        Recommend indices based on slow queries on a view.

        Args:
            view_name: Name of the view

        Returns:
            List of recommended index definitions
        """
        slow_queries = self.get_slow_queries()
        view_slow = [m for m in slow_queries if m.view_name == view_name]

        recommendations = []

        if view_slow:
            avg_time = sum(m.execution_time_ms for m in view_slow) / len(view_slow)
            if avg_time > 5000:  # > 5 seconds
                recommendations.append(
                    f"CREATE INDEX idx_{view_name}_client_id ON {view_name}(client_id) "
                    "(frequently filtered column)"
                )

        return recommendations

    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        original_count = len(self.metrics)

        self.metrics = [
            m for m in self.metrics
            if datetime.fromisoformat(m.timestamp) > cutoff_date
        ]

        removed = original_count - len(self.metrics)
        if removed > 0:
            logger.info(f"Cleaned up {removed} old metrics")


# Global performance monitor instance
_performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return _performance_monitor


def record_query_metrics(
    query_id: str,
    view_name: str,
    execution_time_ms: float,
    result_count: int,
    column_count: int,
    user_role: str,
    tenant_id: str,
    success: bool,
    error_code: Optional[str] = None,
):
    """Record query metrics."""
    metrics = QueryMetrics(
        query_id=query_id,
        view_name=view_name,
        execution_time_ms=execution_time_ms,
        result_count=result_count,
        column_count=column_count,
        timestamp=datetime.utcnow().isoformat(),
        user_role=user_role,
        tenant_id=tenant_id,
        success=success,
        error_code=error_code,
    )
    _performance_monitor.record_query(metrics)
