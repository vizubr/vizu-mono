"""
Allowlist configuration and management for text-to-SQL queries.

This module provides role-based access control (RBAC) for SQL query execution,
enforcing view, column, and aggregate function restrictions per tenant and role.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)


@dataclass
class JoinPath:
    """Defines allowed join paths between views."""
    from_view: str
    to_view: str
    on: str  # Column name used in join condition
    allowed: bool = True


@dataclass
class RoleConfig:
    """Configuration for a specific role within a tenant."""
    views: List[str]  # Allowed views
    columns: Dict[str, List[str]]  # Allowed columns per view; "*" means all
    aggregates: List[str]  # Allowed aggregate functions (COUNT, SUM, AVG, etc.)
    max_rows: int = 10000  # Maximum rows returned per query
    max_execution_time_seconds: int = 30  # Query timeout
    join_paths: List[JoinPath] = field(default_factory=list)  # Allowed joins

    def __post_init__(self):
        """Convert dict join_paths to JoinPath objects if needed."""
        if self.join_paths and isinstance(self.join_paths[0], dict):
            self.join_paths = [
                JoinPath(**jp) if isinstance(jp, dict) else jp
                for jp in self.join_paths
            ]

    def is_view_allowed(self, view_name: str) -> bool:
        """Check if a view is allowed for this role."""
        return view_name in self.views

    def get_allowed_columns(self, view_name: str) -> Set[str]:
        """Get allowed columns for a specific view."""
        if view_name not in self.columns:
            return set()
        cols = self.columns[view_name]
        if "*" in cols:
            return set()  # Empty set signals "all columns allowed"
        return set(cols)

    def is_aggregate_allowed(self, aggregate: str) -> bool:
        """Check if an aggregate function is allowed."""
        return aggregate.upper() in [a.upper() for a in self.aggregates]

    def is_join_allowed(self, from_view: str, to_view: str) -> bool:
        """Check if a join between two views is allowed."""
        for jp in self.join_paths:
            if jp.from_view == from_view and jp.to_view == to_view:
                return jp.allowed
        # If not explicitly defined, disallow by default
        return False


@dataclass
class TenantConfig:
    """Configuration for a specific tenant."""
    name: str
    roles: Dict[str, RoleConfig]

    def get_role_config(self, role: str) -> Optional[RoleConfig]:
        """Get role configuration for this tenant."""
        return self.roles.get(role)

    def is_role_valid(self, role: str) -> bool:
        """Check if a role is defined for this tenant."""
        return role in self.roles

    def get_available_roles(self) -> List[str]:
        """Get list of available roles for this tenant."""
        return list(self.roles.keys())


@dataclass
class AllowlistConfig:
    """Master allowlist configuration for all tenants and roles."""
    version: str = "1.0.0"
    description: str = ""
    default_max_rows: int = 10000
    tenants: Dict[str, TenantConfig] = field(default_factory=dict)

    def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get configuration for a specific tenant, with fallback to 'default'."""
        if tenant_id in self.tenants:
            return self.tenants[tenant_id]
        # Fallback to 'default' template if tenant not explicitly configured
        return self.tenants.get("default")

    def get_role_config(self, tenant_id: str, role: str) -> Optional[RoleConfig]:
        """Get role configuration for tenant and role combination."""
        tenant_config = self.get_tenant_config(tenant_id)
        if tenant_config is None:
            return None
        return tenant_config.get_role_config(role)

    def is_tenant_valid(self, tenant_id: str) -> bool:
        """Check if tenant has a configured allowlist."""
        return self.get_tenant_config(tenant_id) is not None

    def is_role_valid(self, tenant_id: str, role: str) -> bool:
        """Check if role is valid for tenant."""
        tenant_config = self.get_tenant_config(tenant_id)
        if tenant_config is None:
            return False
        return tenant_config.is_role_valid(role)


class AllowlistLoader:
    """Loads and manages allowlist configuration from JSON file."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize loader with optional custom config path.

        Args:
            config_path: Path to allowlist.json. If None, uses default location.
        """
        if config_path is None:
            # Default to config/allowlist.json in this package
            self.config_path = Path(__file__).parent / "config" / "allowlist.json"
        else:
            self.config_path = Path(config_path)

        logger.info(f"AllowlistLoader initialized with config: {self.config_path}")
        self._cache: Optional[AllowlistConfig] = None

    def load(self, force_reload: bool = False) -> AllowlistConfig:
        """
        Load allowlist configuration from JSON file.

        Args:
            force_reload: If True, reload from disk even if cached.

        Returns:
            AllowlistConfig instance.

        Raises:
            FileNotFoundError: If config file not found.
            json.JSONDecodeError: If config file is malformed.
        """
        if self._cache is not None and not force_reload:
            return self._cache

        if not self.config_path.exists():
            raise FileNotFoundError(f"Allowlist config not found: {self.config_path}")

        logger.info(f"Loading allowlist configuration from {self.config_path}")
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse allowlist JSON: {e}")
            raise

        # Parse JSON into AllowlistConfig dataclass
        self._cache = self._parse_config(data)
        return self._cache

    @staticmethod
    def _parse_config(data: Dict[str, Any]) -> AllowlistConfig:
        """
        Parse raw JSON data into AllowlistConfig structure.

        Args:
            data: Raw JSON dictionary.

        Returns:
            AllowlistConfig instance.
        """
        tenants_data = data.get("tenants", {})
        tenants = {}

        for tenant_id, tenant_data in tenants_data.items():
            roles_data = tenant_data.get("roles", {})
            roles = {}

            for role_name, role_data in roles_data.items():
                # Parse join paths
                join_paths = [
                    JoinPath(**jp) for jp in role_data.get("join_paths", [])
                ]

                role_config = RoleConfig(
                    views=role_data.get("views", []),
                    columns=role_data.get("columns", {}),
                    aggregates=role_data.get("aggregates", []),
                    max_rows=role_data.get("max_rows", 10000),
                    max_execution_time_seconds=role_data.get(
                        "max_execution_time_seconds", 30
                    ),
                    join_paths=join_paths,
                )
                roles[role_name] = role_config

            tenant_config = TenantConfig(
                name=tenant_data.get("name", tenant_id), roles=roles
            )
            tenants[tenant_id] = tenant_config

        return AllowlistConfig(
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            default_max_rows=data.get("default_max_rows", 10000),
            tenants=tenants,
        )

    def reload(self) -> AllowlistConfig:
        """Force reload configuration from disk."""
        return self.load(force_reload=True)


# Singleton instance for module-level access
_default_loader: Optional[AllowlistLoader] = None


def get_default_loader() -> AllowlistLoader:
    """Get the default allowlist loader (singleton)."""
    global _default_loader
    if _default_loader is None:
        _default_loader = AllowlistLoader()
    return _default_loader


def get_allowlist_config(force_reload: bool = False) -> AllowlistConfig:
    """
    Convenience function to load allowlist config.

    Args:
        force_reload: If True, reload from disk.

    Returns:
        AllowlistConfig instance.
    """
    loader = get_default_loader()
    return loader.load(force_reload=force_reload)
