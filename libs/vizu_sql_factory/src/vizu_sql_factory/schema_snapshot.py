"""
Schema snapshot generator for safe text-to-SQL queries.

This module provides role-based schema introspection, caching, and filtering
to return only allowed views, columns, and relationships per tenant/role.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple

from vizu_sql_factory.allowlist import (
    AllowlistConfig,
    RoleConfig,
    get_allowlist_config,
)

logger = logging.getLogger(__name__)


@dataclass
class ColumnMetadata:
    """Metadata for a single column in a view."""
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    foreign_key_target: Optional[str] = None  # "view.column" format

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ViewMetadata:
    """Metadata for a single database view."""
    name: str
    columns: List[ColumnMetadata]
    description: Optional[str] = None
    row_count_estimate: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "columns": [col.to_dict() for col in self.columns],
            "description": self.description,
            "row_count_estimate": self.row_count_estimate,
        }


@dataclass
class SchemaSnapshot:
    """Complete schema snapshot for a tenant/role combination."""
    tenant_id: str
    role: str
    views: Dict[str, ViewMetadata] = field(default_factory=dict)
    join_paths: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    constraints: Dict[str, Any] = field(default_factory=dict)  # max_rows, timeout, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)  # cache info, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tenant_id": self.tenant_id,
            "role": self.role,
            "views": {name: view.to_dict() for name, view in self.views.items()},
            "join_paths": self.join_paths,
            "generated_at": self.generated_at.isoformat(),
            "constraints": self.constraints,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @property
    def view_names(self) -> List[str]:
        """Get list of view names in snapshot."""
        return list(self.views.keys())

    @property
    def total_columns(self) -> int:
        """Get total number of columns across all views."""
        return sum(len(view.columns) for view in self.views.values())


@dataclass
class CacheEntry:
    """Cache entry for schema snapshot."""
    snapshot: SchemaSnapshot
    cached_at: datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        elapsed = (datetime.utcnow() - self.cached_at).total_seconds()
        return elapsed > self.ttl_seconds

    def age_seconds(self) -> int:
        """Get age of cache entry in seconds."""
        return int((datetime.utcnow() - self.cached_at).total_seconds())


class SchemaSnapshotGenerator:
    """
    Generates filtered schema snapshots for text-to-SQL queries.

    Responsibilities:
    - Introspect database schema (views, columns, relationships)
    - Filter by allowlist (views/columns per role/tenant)
    - Cache snapshots with TTL
    - Return structured snapshot for LLM prompting
    """

    def __init__(
        self,
        supabase_client=None,
        allowlist_config: Optional[AllowlistConfig] = None,
        cache_ttl_seconds: int = 3600,
    ):
        """
        Initialize the schema snapshot generator.

        Args:
            supabase_client: Supabase client for introspection (can be None for testing).
            allowlist_config: AllowlistConfig instance. If None, loads default.
            cache_ttl_seconds: Cache expiry time in seconds (default 1 hour).
        """
        self.supabase_client = supabase_client
        self.allowlist_config = allowlist_config or get_allowlist_config()
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        logger.info(f"SchemaSnapshotGenerator initialized (TTL={cache_ttl_seconds}s)")

    def _cache_key(self, tenant_id: str, role: str) -> str:
        """Generate cache key for tenant/role combination."""
        return f"{tenant_id}:{role}"

    def generate(
        self,
        tenant_id: str,
        role: str,
        force_refresh: bool = False,
    ) -> Optional[SchemaSnapshot]:
        """
        Generate or retrieve cached schema snapshot for tenant/role.

        Args:
            tenant_id: Tenant identifier.
            role: User role.
            force_refresh: Force regeneration even if cached.

        Returns:
            SchemaSnapshot if successful, None if tenant/role not configured.

        Raises:
            ValueError: If introspection fails or role is invalid.
        """
        # Validate tenant and role against allowlist
        if not self.allowlist_config.is_tenant_valid(tenant_id):
            logger.warning(f"Tenant not configured in allowlist: {tenant_id}")
            return None

        if not self.allowlist_config.is_role_valid(tenant_id, role):
            logger.warning(f"Role not valid for tenant {tenant_id}: {role}")
            return None

        # Check cache
        cache_key = self._cache_key(tenant_id, role)
        if not force_refresh and cache_key in self._cache:
            cached = self._cache[cache_key]
            if not cached.is_expired():
                logger.debug(
                    f"Cache hit for {cache_key} (age={cached.age_seconds()}s)"
                )
                cached.snapshot.metadata["cache_age_seconds"] = cached.age_seconds()
                return cached.snapshot
            else:
                logger.debug(f"Cache expired for {cache_key}")
                del self._cache[cache_key]

        # Generate snapshot
        logger.info(f"Generating schema snapshot for {tenant_id}/{role}")
        snapshot = self._build_snapshot(tenant_id, role)

        # Cache result
        if snapshot:
            self._cache[cache_key] = CacheEntry(
                snapshot=snapshot,
                cached_at=datetime.utcnow(),
                ttl_seconds=self.cache_ttl_seconds,
            )
            logger.debug(f"Cached snapshot for {cache_key}")

        return snapshot

    def _build_snapshot(self, tenant_id: str, role: str) -> SchemaSnapshot:
        """
        Build schema snapshot by introspecting and filtering.

        Args:
            tenant_id: Tenant identifier.
            role: User role.

        Returns:
            SchemaSnapshot instance.
        """
        role_config = self.allowlist_config.get_role_config(tenant_id, role)
        if not role_config:
            raise ValueError(f"No role config for {tenant_id}/{role}")

        # Get all schema info (in production, this would query information_schema)
        all_views = self._introspect_views()

        # Filter by allowlist
        filtered_views = self._filter_views(all_views, role_config)

        # Build snapshot
        snapshot = SchemaSnapshot(
            tenant_id=tenant_id,
            role=role,
            views=filtered_views,
            join_paths=self._build_join_paths(role_config, filtered_views),
            constraints={
                "max_rows": role_config.max_rows,
                "max_execution_time_seconds": role_config.max_execution_time_seconds,
                "allowed_aggregates": role_config.aggregates,
            },
            metadata={
                "generated_at": datetime.utcnow().isoformat(),
                "view_count": len(filtered_views),
                "column_count": sum(len(v.columns) for v in filtered_views.values()),
            },
        )

        return snapshot

    def _introspect_views(self) -> Dict[str, ViewMetadata]:
        """
        Introspect database for all available views.

        In production, this would query PostgreSQL information_schema.
        For now, returns mock view definitions based on schema audit.

        Returns:
            Dict mapping view name to ViewMetadata.
        """
        # Mock data based on Phase 0.1 audit and planned views
        views: Dict[str, ViewMetadata] = {
            "customers_view": ViewMetadata(
                name="customers_view",
                columns=[
                    ColumnMetadata(name="id", data_type="integer", is_primary_key=True),
                    ColumnMetadata(name="id_externo", data_type="varchar"),
                    ColumnMetadata(name="nome", data_type="varchar"),
                    ColumnMetadata(name="created_at", data_type="timestamp"),
                    ColumnMetadata(
                        name="cliente_vizu_id",
                        data_type="uuid",
                        foreign_key_target="cliente_vizu.id",
                    ),
                ],
                description="Customer records per tenant",
                row_count_estimate=5000,
            ),
            "data_sources_summary_view": ViewMetadata(
                name="data_sources_summary_view",
                columns=[
                    ColumnMetadata(name="id", data_type="integer", is_primary_key=True),
                    ColumnMetadata(name="tipo_fonte", data_type="varchar"),
                    ColumnMetadata(name="caminho", data_type="varchar"),
                    ColumnMetadata(name="created_at", data_type="timestamp"),
                    ColumnMetadata(
                        name="cliente_vizu_id",
                        data_type="uuid",
                        foreign_key_target="cliente_vizu.id",
                    ),
                ],
                description="Data sources used for RAG",
                row_count_estimate=100,
            ),
            "service_credentials_list_view": ViewMetadata(
                name="service_credentials_list_view",
                columns=[
                    ColumnMetadata(name="id", data_type="integer", is_primary_key=True),
                    ColumnMetadata(name="nome_servico", data_type="varchar"),
                    ColumnMetadata(name="is_active", data_type="boolean"),
                    ColumnMetadata(
                        name="cliente_vizu_id",
                        data_type="uuid",
                        foreign_key_target="cliente_vizu.id",
                    ),
                ],
                description="External service integrations (admin only)",
                row_count_estimate=20,
            ),
            "tenant_config_view": ViewMetadata(
                name="tenant_config_view",
                columns=[
                    ColumnMetadata(
                        name="horario_funcionamento", data_type="jsonb"
                    ),
                    ColumnMetadata(
                        name="ferramenta_rag_habilitada", data_type="boolean"
                    ),
                    ColumnMetadata(
                        name="ferramenta_sql_habilitada", data_type="boolean"
                    ),
                    ColumnMetadata(
                        name="ferramenta_agendamento_habilitada", data_type="boolean"
                    ),
                    ColumnMetadata(
                        name="cliente_vizu_id",
                        data_type="uuid",
                        foreign_key_target="cliente_vizu.id",
                    ),
                ],
                description="Readable tenant configuration",
                row_count_estimate=1,
            ),
        }

        return views

    def _filter_views(
        self,
        all_views: Dict[str, ViewMetadata],
        role_config: RoleConfig,
    ) -> Dict[str, ViewMetadata]:
        """
        Filter views and columns based on role allowlist.

        Args:
            all_views: All available views.
            role_config: Role configuration with allowed views/columns.

        Returns:
            Filtered views dict.
        """
        filtered = {}

        for view_name in role_config.views:
            if view_name not in all_views:
                logger.warning(f"View in allowlist not found in schema: {view_name}")
                continue

            full_view = all_views[view_name]
            allowed_columns = role_config.get_allowed_columns(view_name)

            # If allowed_columns is empty set, it means "*" (all columns)
            if allowed_columns == set():
                # Include all columns
                filtered[view_name] = full_view
            else:
                # Filter columns
                filtered_cols = [
                    col
                    for col in full_view.columns
                    if col.name in allowed_columns
                ]
                filtered[view_name] = ViewMetadata(
                    name=full_view.name,
                    columns=filtered_cols,
                    description=full_view.description,
                    row_count_estimate=full_view.row_count_estimate,
                )

        return filtered

    def _build_join_paths(
        self,
        role_config: RoleConfig,
        filtered_views: Dict[str, ViewMetadata],
    ) -> List[Dict[str, Any]]:
        """
        Build list of allowed join paths between views.

        Args:
            role_config: Role configuration.
            filtered_views: Filtered views (to validate references).

        Returns:
            List of join path definitions.
        """
        join_paths = []

        for jp in role_config.join_paths:
            # Validate join references filtered views
            if jp.from_view not in filtered_views or jp.to_view not in filtered_views:
                logger.debug(
                    f"Skipping join path {jp.from_view}->{jp.to_view} (not in filtered views)"
                )
                continue

            if jp.allowed:
                join_paths.append(
                    {
                        "from_view": jp.from_view,
                        "to_view": jp.to_view,
                        "on_column": jp.on,
                        "allowed": True,
                    }
                )

        return join_paths

    def cache_info(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "entries": len(self._cache),
            "ttl_seconds": self.cache_ttl_seconds,
            "cached_keys": [
                {
                    "key": key,
                    "age_seconds": entry.age_seconds(),
                    "expired": entry.is_expired(),
                }
                for key, entry in self._cache.items()
            ],
        }

    def clear_cache(self, tenant_id: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            tenant_id: If provided, clear only entries for this tenant.
                      If None, clear entire cache.

        Returns:
            Number of entries cleared.
        """
        if tenant_id is None:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared entire cache ({count} entries)")
            return count

        prefix = f"{tenant_id}:"
        count = 0
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]
            count += 1

        logger.info(f"Cleared {count} cache entries for tenant {tenant_id}")
        return count


class SchemaSnapshotFormatter:
    """Formats schema snapshots for LLM prompting."""

    @staticmethod
    def format_for_prompt(snapshot: SchemaSnapshot) -> str:
        """
        Format schema snapshot as markdown for inclusion in LLM prompt.

        Args:
            snapshot: SchemaSnapshot instance.

        Returns:
            Formatted markdown string.
        """
        lines = []

        lines.append(f"## Schema for {snapshot.tenant_id} ({snapshot.role} role)\n")
        lines.append(f"Generated: {snapshot.generated_at.isoformat()}\n")
        lines.append(f"Constraints:")
        lines.append(f"- Max rows per query: {snapshot.constraints.get('max_rows', 'N/A')}")
        lines.append(
            f"- Max execution time: {snapshot.constraints.get('max_execution_time_seconds', 'N/A')}s"
        )
        lines.append(f"- Allowed aggregates: {', '.join(snapshot.constraints.get('allowed_aggregates', []))}\n")

        lines.append("### Views\n")
        for view_name, view in snapshot.views.items():
            lines.append(f"#### `{view_name}`")
            if view.description:
                lines.append(f"{view.description}\n")
            lines.append("**Columns:**")
            for col in view.columns:
                fk_info = f" → `{col.foreign_key_target}`" if col.foreign_key_target else ""
                nullable = " (nullable)" if col.nullable else " (required)"
                lines.append(f"- `{col.name}`: {col.data_type}{nullable}{fk_info}")
            lines.append("")

        if snapshot.join_paths:
            lines.append("\n### Allowed Joins\n")
            for jp in snapshot.join_paths:
                lines.append(
                    f"- `{jp['from_view']}` ↔ `{jp['to_view']}` on `{jp['on_column']}`"
                )

        return "\n".join(lines)

    @staticmethod
    def format_as_json(snapshot: SchemaSnapshot) -> str:
        """Format snapshot as JSON."""
        return snapshot.to_json()
