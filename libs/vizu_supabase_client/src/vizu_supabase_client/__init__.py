"""
Vizu Supabase Client - SDK wrapper for Supabase operations.

Provides a singleton client for database operations via Supabase REST API.
"""
from .client import (
    get_supabase_client,
    get_async_supabase_client,
    close_supabase_client,
    SupabaseConfig,
)
from .crud import SupabaseCRUD
from .auth_context import (
    AuthContext,
    JWTContextExtractor,
    get_jwt_extractor,
)
from .postgrest_executor import (
    QueryResult,
    PostgRESTQueryExecutor,
    get_postgrest_executor,
)

__all__ = [
    # Client
    "get_supabase_client",
    "get_async_supabase_client",
    "close_supabase_client",
    "SupabaseConfig",
    # CRUD
    "SupabaseCRUD",
    # Auth Context
    "AuthContext",
    "JWTContextExtractor",
    "get_jwt_extractor",
    # PostgREST Executor
    "QueryResult",
    "PostgRESTQueryExecutor",
    "get_postgrest_executor",
]
