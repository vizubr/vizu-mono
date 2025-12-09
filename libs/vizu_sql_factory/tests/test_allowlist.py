"""
Unit tests for allowlist configuration and role filtering.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from vizu_sql_factory.allowlist import (
    JoinPath,
    RoleConfig,
    TenantConfig,
    AllowlistConfig,
    AllowlistLoader,
    get_allowlist_config,
)


class TestJoinPath:
    """Tests for JoinPath dataclass."""

    def test_join_path_creation(self):
        """Test basic join path creation."""
        jp = JoinPath(
            from_view="customers_view",
            to_view="orders_view",
            on="customer_id",
            allowed=True,
        )
        assert jp.from_view == "customers_view"
        assert jp.to_view == "orders_view"
        assert jp.on == "customer_id"
        assert jp.allowed is True

    def test_join_path_default_allowed(self):
        """Test default allowed=True."""
        jp = JoinPath(
            from_view="a", to_view="b", on="col"
        )
        assert jp.allowed is True


class TestRoleConfig:
    """Tests for RoleConfig dataclass."""

    def test_role_config_creation(self):
        """Test basic role config creation."""
        rc = RoleConfig(
            views=["customers_view"],
            columns={"customers_view": ["id", "name"]},
            aggregates=["COUNT", "SUM"],
            max_rows=1000,
            max_execution_time_seconds=30,
        )
        assert rc.views == ["customers_view"]
        assert rc.max_rows == 1000

    def test_is_view_allowed(self):
        """Test view allowance check."""
        rc = RoleConfig(
            views=["customers_view", "orders_view"],
            columns={},
            aggregates=[],
        )
        assert rc.is_view_allowed("customers_view") is True
        assert rc.is_view_allowed("admin_view") is False

    def test_get_allowed_columns_specific(self):
        """Test getting specific allowed columns."""
        rc = RoleConfig(
            views=["customers_view"],
            columns={"customers_view": ["id", "name", "email"]},
            aggregates=[],
        )
        cols = rc.get_allowed_columns("customers_view")
        assert cols == {"id", "name", "email"}

    def test_get_allowed_columns_wildcard(self):
        """Test wildcard '*' returns empty set (all allowed)."""
        rc = RoleConfig(
            views=["customers_view"],
            columns={"customers_view": ["*"]},
            aggregates=[],
        )
        cols = rc.get_allowed_columns("customers_view")
        assert cols == set()  # Empty set signals "all columns allowed"

    def test_get_allowed_columns_missing_view(self):
        """Test getting columns for non-configured view."""
        rc = RoleConfig(
            views=["customers_view"],
            columns={"other_view": ["id"]},
            aggregates=[],
        )
        cols = rc.get_allowed_columns("customers_view")
        assert cols == set()

    def test_is_aggregate_allowed(self):
        """Test aggregate function allowance check."""
        rc = RoleConfig(
            views=[],
            columns={},
            aggregates=["COUNT", "SUM", "AVG"],
        )
        assert rc.is_aggregate_allowed("COUNT") is True
        assert rc.is_aggregate_allowed("count") is True  # Case-insensitive
        assert rc.is_aggregate_allowed("MAX") is False

    def test_is_join_allowed_explicit_allowed(self):
        """Test join allowance for explicitly allowed path."""
        jp = JoinPath(from_view="a", to_view="b", on="id", allowed=True)
        rc = RoleConfig(
            views=["a", "b"],
            columns={},
            aggregates=[],
            join_paths=[jp],
        )
        assert rc.is_join_allowed("a", "b") is True

    def test_is_join_allowed_explicit_disallowed(self):
        """Test join disallowance for explicitly disallowed path."""
        jp = JoinPath(from_view="a", to_view="b", on="id", allowed=False)
        rc = RoleConfig(
            views=["a", "b"],
            columns={},
            aggregates=[],
            join_paths=[jp],
        )
        assert rc.is_join_allowed("a", "b") is False

    def test_is_join_allowed_implicit_disallowed(self):
        """Test join disallowance for undefined path (implicit)."""
        rc = RoleConfig(
            views=["a", "b"],
            columns={},
            aggregates=[],
            join_paths=[],
        )
        assert rc.is_join_allowed("a", "b") is False


class TestTenantConfig:
    """Tests for TenantConfig dataclass."""

    def test_tenant_config_creation(self):
        """Test basic tenant config creation."""
        analyst_role = RoleConfig(
            views=["customers_view"],
            columns={},
            aggregates=["COUNT"],
        )
        tc = TenantConfig(
            name="Acme Corp",
            roles={"analyst": analyst_role},
        )
        assert tc.name == "Acme Corp"
        assert "analyst" in tc.roles

    def test_get_role_config(self):
        """Test retrieving role config."""
        analyst_role = RoleConfig(
            views=["customers_view"],
            columns={},
            aggregates=["COUNT"],
        )
        tc = TenantConfig(
            name="Test",
            roles={"analyst": analyst_role},
        )
        retrieved = tc.get_role_config("analyst")
        assert retrieved is analyst_role
        assert tc.get_role_config("admin") is None

    def test_is_role_valid(self):
        """Test role validity check."""
        analyst_role = RoleConfig(
            views=[],
            columns={},
            aggregates=[],
        )
        tc = TenantConfig(
            name="Test",
            roles={"analyst": analyst_role},
        )
        assert tc.is_role_valid("analyst") is True
        assert tc.is_role_valid("admin") is False

    def test_get_available_roles(self):
        """Test retrieving available roles."""
        analyst_role = RoleConfig(views=[], columns={}, aggregates=[])
        viewer_role = RoleConfig(views=[], columns={}, aggregates=[])
        tc = TenantConfig(
            name="Test",
            roles={"analyst": analyst_role, "viewer": viewer_role},
        )
        roles = tc.get_available_roles()
        assert set(roles) == {"analyst", "viewer"}


class TestAllowlistConfig:
    """Tests for AllowlistConfig dataclass."""

    def test_allowlist_config_creation(self):
        """Test basic allowlist config creation."""
        rc = RoleConfig(views=[], columns={}, aggregates=[])
        tc = TenantConfig(name="Test", roles={"analyst": rc})
        ac = AllowlistConfig(
            version="1.0.0",
            description="Test allowlist",
            tenants={"tenant1": tc},
        )
        assert ac.version == "1.0.0"
        assert "tenant1" in ac.tenants

    def test_get_tenant_config_existing(self):
        """Test getting existing tenant config."""
        rc = RoleConfig(views=[], columns={}, aggregates=[])
        tc = TenantConfig(name="Test", roles={"analyst": rc})
        ac = AllowlistConfig(tenants={"tenant1": tc})
        retrieved = ac.get_tenant_config("tenant1")
        assert retrieved is tc

    def test_get_tenant_config_fallback_default(self):
        """Test fallback to 'default' tenant when not found."""
        rc = RoleConfig(views=[], columns={}, aggregates=[])
        default_tc = TenantConfig(name="Default", roles={"analyst": rc})
        ac = AllowlistConfig(tenants={"default": default_tc})
        # Request non-existent tenant should fallback to 'default'
        retrieved = ac.get_tenant_config("unknown_tenant")
        assert retrieved is default_tc

    def test_get_tenant_config_none(self):
        """Test getting tenant config when no tenant or default exists."""
        ac = AllowlistConfig(tenants={})
        assert ac.get_tenant_config("unknown") is None

    def test_get_role_config(self):
        """Test getting role config for tenant+role."""
        analyst_role = RoleConfig(
            views=["customers_view"],
            columns={},
            aggregates=["COUNT"],
        )
        tc = TenantConfig(name="Test", roles={"analyst": analyst_role})
        ac = AllowlistConfig(tenants={"tenant1": tc})
        retrieved = ac.get_role_config("tenant1", "analyst")
        assert retrieved is analyst_role

    def test_get_role_config_nonexistent_tenant(self):
        """Test getting role config for non-existent tenant."""
        ac = AllowlistConfig(tenants={})
        assert ac.get_role_config("unknown", "analyst") is None

    def test_is_tenant_valid(self):
        """Test tenant validity check."""
        rc = RoleConfig(views=[], columns={}, aggregates=[])
        tc = TenantConfig(name="Test", roles={"analyst": rc})
        ac = AllowlistConfig(tenants={"tenant1": tc})
        assert ac.is_tenant_valid("tenant1") is True
        assert ac.is_tenant_valid("unknown") is False

    def test_is_role_valid(self):
        """Test role validity for tenant+role combo."""
        rc = RoleConfig(views=[], columns={}, aggregates=[])
        tc = TenantConfig(name="Test", roles={"analyst": rc})
        ac = AllowlistConfig(tenants={"tenant1": tc})
        assert ac.is_role_valid("tenant1", "analyst") is True
        assert ac.is_role_valid("tenant1", "admin") is False
        assert ac.is_role_valid("unknown", "analyst") is False


class TestAllowlistLoader:
    """Tests for AllowlistLoader class."""

    def test_loader_initialization_default_path(self):
        """Test loader initialization with default path."""
        loader = AllowlistLoader()
        expected_path = Path(__file__).parent.parent / "vizu_sql_factory" / "config" / "allowlist.json"
        assert loader.config_path == expected_path

    def test_loader_initialization_custom_path(self):
        """Test loader initialization with custom path."""
        custom_path = "/custom/path/allowlist.json"
        loader = AllowlistLoader(custom_path)
        assert loader.config_path == Path(custom_path)

    def test_load_valid_config(self, tmp_path):
        """Test loading valid configuration."""
        config_data = {
            "version": "1.0.0",
            "description": "Test config",
            "default_max_rows": 10000,
            "tenants": {
                "tenant1": {
                    "name": "Test Tenant",
                    "roles": {
                        "analyst": {
                            "views": ["customers_view"],
                            "columns": {"customers_view": ["id", "name"]},
                            "aggregates": ["COUNT"],
                            "max_rows": 5000,
                            "max_execution_time_seconds": 30,
                            "join_paths": []
                        }
                    }
                }
            }
        }
        config_file = tmp_path / "allowlist.json"
        config_file.write_text(json.dumps(config_data))

        loader = AllowlistLoader(str(config_file))
        config = loader.load()

        assert config.version == "1.0.0"
        assert "tenant1" in config.tenants
        assert config.tenants["tenant1"].name == "Test Tenant"

    def test_load_nonexistent_file(self):
        """Test loading from non-existent file."""
        loader = AllowlistLoader("/nonexistent/allowlist.json")
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_load_malformed_json(self, tmp_path):
        """Test loading malformed JSON."""
        config_file = tmp_path / "allowlist.json"
        config_file.write_text("{ invalid json")

        loader = AllowlistLoader(str(config_file))
        with pytest.raises(json.JSONDecodeError):
            loader.load()

    def test_load_caching(self, tmp_path):
        """Test that config is cached after first load."""
        config_data = {
            "version": "1.0.0",
            "tenants": {},
        }
        config_file = tmp_path / "allowlist.json"
        config_file.write_text(json.dumps(config_data))

        loader = AllowlistLoader(str(config_file))
        config1 = loader.load()
        config2 = loader.load()

        assert config1 is config2  # Same object (cached)

    def test_reload_bypasses_cache(self, tmp_path):
        """Test that reload() forces reload from disk."""
        config_data_v1 = {
            "version": "1.0.0",
            "description": "v1",
            "tenants": {},
        }
        config_file = tmp_path / "allowlist.json"
        config_file.write_text(json.dumps(config_data_v1))

        loader = AllowlistLoader(str(config_file))
        config1 = loader.load()
        assert config1.description == "v1"

        # Update file
        config_data_v2 = {
            "version": "1.0.1",
            "description": "v2",
            "tenants": {},
        }
        config_file.write_text(json.dumps(config_data_v2))

        # Reload should get new version
        config2 = loader.reload()
        assert config2.description == "v2"

    def test_parse_config_with_join_paths(self):
        """Test parsing config with join paths."""
        config_data = {
            "version": "1.0.0",
            "tenants": {
                "tenant1": {
                    "name": "Test",
                    "roles": {
                        "analyst": {
                            "views": ["customers", "orders"],
                            "columns": {},
                            "aggregates": [],
                            "join_paths": [
                                {
                                    "from_view": "customers",
                                    "to_view": "orders",
                                    "on": "customer_id",
                                    "allowed": True
                                }
                            ]
                        }
                    }
                }
            }
        }
        config = AllowlistLoader._parse_config(config_data)
        role = config.tenants["tenant1"].roles["analyst"]
        assert len(role.join_paths) == 1
        assert role.join_paths[0].from_view == "customers"
        assert role.join_paths[0].allowed is True


class TestAllowlistFiltering:
    """Integration tests for role-based filtering."""

    def test_analyst_vs_viewer_column_filtering(self):
        """Test that analyst and viewer roles have different column access."""
        analyst_role = RoleConfig(
            views=["customers_view"],
            columns={"customers_view": ["id", "name", "email", "created_at"]},
            aggregates=["COUNT", "SUM", "AVG"],
            max_rows=10000,
        )
        viewer_role = RoleConfig(
            views=["customers_view"],
            columns={"customers_view": ["id", "name"]},
            aggregates=["COUNT"],
            max_rows=1000,
        )

        analyst_cols = analyst_role.get_allowed_columns("customers_view")
        viewer_cols = viewer_role.get_allowed_columns("customers_view")

        assert "email" in analyst_cols
        assert "email" not in viewer_cols
        assert analyst_role.max_rows > viewer_role.max_rows

    def test_admin_role_has_all_views(self):
        """Test that admin role has access to all views and columns."""
        admin_role = RoleConfig(
            views=["customers_view", "orders_view", "admin_view"],
            columns={
                "customers_view": ["*"],
                "orders_view": ["*"],
                "admin_view": ["*"],
            },
            aggregates=["COUNT", "SUM", "AVG", "MIN", "MAX"],
            max_rows=100000,
        )

        assert admin_role.is_view_allowed("customers_view")
        assert admin_role.is_view_allowed("admin_view")
        assert admin_role.get_allowed_columns("customers_view") == set()  # "*" = all
        assert admin_role.max_rows == 100000


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_allowlist_config(self, monkeypatch, tmp_path):
        """Test get_allowlist_config convenience function."""
        config_data = {
            "version": "1.0.0",
            "tenants": {
                "test": {
                    "name": "Test",
                    "roles": {
                        "analyst": {
                            "views": ["customers_view"],
                            "columns": {},
                            "aggregates": ["COUNT"],
                            "max_rows": 1000,
                            "max_execution_time_seconds": 30,
                            "join_paths": []
                        }
                    }
                }
            }
        }
        config_file = tmp_path / "allowlist.json"
        config_file.write_text(json.dumps(config_data))

        # Monkeypatch the default loader path
        monkeypatch.setattr(
            "vizu_sql_factory.allowlist.AllowlistLoader",
            lambda path=None: AllowlistLoader(str(config_file) if path is None else path)
        )

        config = get_allowlist_config()
        assert config.version == "1.0.0"
        assert "test" in config.tenants
