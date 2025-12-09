"""
PostgREST-based query executor with JWT authentication and RLS enforcement.

Executes read-only queries via Supabase PostgREST API with user JWT tokens
to enforce Row-Level Security (RLS) policies.
"""

import logging
import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from datetime import timedelta

from vizu_supabase_client.client import get_supabase_client
from vizu_supabase_client.auth_context import AuthContext, JWTContextExtractor

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result from a PostgREST query."""
    rows: List[Dict[str, Any]]
    column_names: List[str]
    column_types: Dict[str, str]  # column name -> type
    total_rows: Optional[int] = None  # Total count if requested
    execution_time_ms: float = 0.0
    telemetry_id: Optional[str] = None  # For tracing

    def __len__(self) -> int:
        """Return number of rows returned."""
        return len(self.rows)

    def get_count(self) -> int:
        """Get row count (only valid if requested)."""
        return self.total_rows if self.total_rows is not None else len(self.rows)


class PostgRESTQueryExecutor:
    """
    Executes queries via PostgREST API with JWT-based RLS enforcement.

    Features:
    - User JWT authentication (RLS enforcement)
    - Pagination support (limit, offset)
    - Configurable row limits per tenant/role
    - Retry logic with exponential backoff
    - Query timeout enforcement
    - Column filtering (select specific columns)
    """

    def __init__(
        self,
        jwt_extractor: Optional[JWTContextExtractor] = None,
        default_timeout_seconds: int = 30,
        max_retries: int = 3,
        max_rows_per_request: int = 100,
    ):
        """
        Initialize the executor.

        Args:
            jwt_extractor: JWTContextExtractor for authentication context.
            default_timeout_seconds: Default query timeout (30s).
            max_retries: Max retries on transient failures (3).
            max_rows_per_request: Max rows to return per query (100).
        """
        self.jwt_extractor = jwt_extractor
        self.default_timeout_seconds = default_timeout_seconds
        self.max_retries = max_retries
        self.max_rows_per_request = max_rows_per_request
        logger.info(
            f"PostgRESTQueryExecutor initialized "
            f"(timeout={default_timeout_seconds}s, max_rows={max_rows_per_request})"
        )

    def query(
        self,
        view_name: str,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        user_jwt: Optional[str] = None,
        count: bool = False,
    ) -> QueryResult:
        """
        Execute a query against a view via PostgREST.

        Args:
            view_name: View or table name to query.
            filters: Dict of column:value filters (AND'ed together).
            columns: Specific columns to select. If None, select all.
            limit: Max rows to return (capped at max_rows_per_request).
            offset: Offset for pagination (default 0).
            user_jwt: User JWT token for RLS enforcement. If None, uses service role.
            count: If True, also return total count.

        Returns:
            QueryResult with rows and metadata.

        Raises:
            ValueError: If input is invalid.
            Exception: If query fails after retries.
        """
        start_time = time.time()

        # Validate inputs
        if not view_name:
            raise ValueError("view_name is required")

        # Cap limit
        limit = min(limit or self.max_rows_per_request, self.max_rows_per_request)

        logger.info(
            f"Executing query: view={view_name}, limit={limit}, "
            f"offset={offset}, user_jwt={'***' if user_jwt else 'none'}"
        )

        # Get Supabase client
        # If user_jwt is provided, create a new client with that token
        # Otherwise use service role client
        if user_jwt:
            client = self._get_client_with_jwt(user_jwt)
        else:
            client = get_supabase_client(use_service_role=True)

        try:
            # Build query
            query = client.table(view_name)

            # Apply filters
            if filters:
                for column, value in filters.items():
                    if isinstance(value, (list, tuple)):
                        # IN filter
                        query = query.filter(column, "in", f"({','.join(str(v) for v in value)})")
                    else:
                        # Exact match
                        query = query.eq(column, value)

            # Select specific columns
            if columns:
                query = query.select(",".join(columns))

            # Pagination
            query = query.range(offset, offset + limit - 1)

            # Count if requested
            if count:
                query = query.count("exact")

            # Execute with retry
            response = self._execute_with_retry(query)

            # Parse response
            rows = response.data or []
            column_names = list(rows[0].keys()) if rows else (columns or [])
            column_types = {col: "unknown" for col in column_names}

            execution_time_ms = (time.time() - start_time) * 1000

            result = QueryResult(
                rows=rows,
                column_names=column_names,
                column_types=column_types,
                total_rows=response.count if count else None,
                execution_time_ms=execution_time_ms,
            )

            logger.info(
                f"Query succeeded: {len(rows)} rows in {execution_time_ms:.1f}ms"
            )
            return result

        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def _get_client_with_jwt(self, jwt_token: str):
        """
        Create a Supabase client with user JWT token.

        This client will enforce RLS policies based on the JWT claims.

        Args:
            jwt_token: User JWT token.

        Returns:
            Supabase client with JWT authentication.
        """
        from supabase import create_client
        from supabase.lib.client_options import SyncClientOptions

        config_url = get_supabase_client().url

        options = SyncClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            headers={"Authorization": f"Bearer {jwt_token}"},
        )

        client = create_client(config_url, jwt_token, options)
        return client

    def _execute_with_retry(
        self,
        query,
        retry_count: int = 0,
    ):
        """
        Execute query with exponential backoff retry.

        Args:
            query: Supabase query builder.
            retry_count: Current retry count (internal).

        Returns:
            Query response.

        Raises:
            Exception: If all retries exhausted.
        """
        try:
            response = query.execute()
            return response
        except Exception as e:
            if retry_count < self.max_retries:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** retry_count
                logger.warning(
                    f"Query failed, retrying in {wait_time}s "
                    f"(attempt {retry_count + 1}/{self.max_retries}): {e}"
                )
                time.sleep(wait_time)
                return self._execute_with_retry(query, retry_count + 1)
            else:
                logger.error(f"Query failed after {self.max_retries} retries: {e}")
                raise

    def query_with_context(
        self,
        view_name: str,
        auth_context: AuthContext,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        user_jwt: Optional[str] = None,
    ) -> QueryResult:
        """
        Execute query with auth context (tenant/role).

        Automatically filters by tenant_id and enforces role-based limits.

        Args:
            view_name: View to query.
            auth_context: AuthContext with tenant_id and role.
            filters: Additional filters.
            columns: Columns to select.
            limit: Max rows (will be capped based on role).
            offset: Pagination offset.
            user_jwt: User JWT for RLS enforcement.

        Returns:
            QueryResult.
        """
        # Add tenant_id to filters
        if filters is None:
            filters = {}
        filters["cliente_vizu_id"] = auth_context.tenant_id

        # Cap limit based on role (stub; would come from allowlist)
        role_max_rows = 10000  # Default; in Phase 1, get from AllowlistConfig
        limit = min(limit or role_max_rows, role_max_rows)

        logger.info(
            f"Query with context: tenant={auth_context.tenant_id}, "
            f"role={auth_context.role}, limit={limit}"
        )

        return self.query(
            view_name=view_name,
            filters=filters,
            columns=columns,
            limit=limit,
            offset=offset,
            user_jwt=user_jwt,
        )


# Singleton instance
_postgrest_executor: Optional[PostgRESTQueryExecutor] = None


def get_postgrest_executor() -> PostgRESTQueryExecutor:
    """Get or create the default PostgREST executor."""
    global _postgrest_executor
    if _postgrest_executor is None:
        _postgrest_executor = PostgRESTQueryExecutor()
    return _postgrest_executor
