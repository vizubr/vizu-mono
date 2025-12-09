"""
Unit and integration tests for schema snapshot generator.
"""

import pytest
import json
from datetime import datetime, timedelta

from vizu_sql_factory.schema_snapshot import (
    ColumnMetadata,
    ViewMetadata,
    SchemaSnapshot,
    CacheEntry,
    SchemaSnapshotGenerator,
    SchemaSnapshotFormatter,
)
from vizu_sql_factory.allowlist import (
    AllowlistConfig,
    RoleConfig,
    TenantConfig,
    JoinPath,
)


class TestColumnMetadata:
    """Tests for ColumnMetadata."""

    def test_column_metadata_basic(self):
        """Test basic column metadata creation."""
        col = ColumnMetadata(
            name="id",
            data_type="integer",
            nullable=False,
            is_primary_key=True,
        )
        assert col.name == "id"
        assert col.data_type == "integer"
        assert col.nullable is False
        assert col.is_primary_key is True

    def test_column_metadata_with_fk(self):
        """Test column metadata with foreign key reference."""
        col = ColumnMetadata(
            name="customer_id",
            data_type="uuid",
            foreign_key_target="customers_view.id",
        )
        assert col.foreign_key_target == "customers_view.id"

    def test_column_metadata_to_dict(self):
        """Test conversion to dict."""
        col = ColumnMetadata(
            name="name",
            data_type="varchar",
            nullable=True,
        )
        d = col.to_dict()
        assert d["name"] == "name"
        assert d["data_type"] == "varchar"
        assert d["nullable"] is True


class TestViewMetadata:
    """Tests for ViewMetadata."""

    def test_view_metadata_basic(self):
        """Test basic view metadata creation."""
        cols = [
            ColumnMetadata(name="id", data_type="integer", is_primary_key=True),
            ColumnMetadata(name="name", data_type="varchar"),
        ]
        view = ViewMetadata(
            name="customers_view",
            columns=cols,
            description="Customer data",
            row_count_estimate=1000,
        )
        assert view.name == "customers_view"
        assert len(view.columns) == 2
        assert view.row_count_estimate == 1000

    def test_view_metadata_to_dict(self):
        """Test conversion to dict."""
        cols = [ColumnMetadata(name="id", data_type="integer")]
        view = ViewMetadata(name="test_view", columns=cols)
        d = view.to_dict()
        assert d["name"] == "test_view"
        assert len(d["columns"]) == 1


class TestSchemaSnapshot:
    """Tests for SchemaSnapshot."""

    def test_schema_snapshot_creation(self):
        """Test basic schema snapshot creation."""
        view = ViewMetadata(
            name="customers_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        snapshot = SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"customers_view": view},
        )
        assert snapshot.tenant_id == "tenant1"
        assert snapshot.role == "analyst"
        assert "customers_view" in snapshot.views

    def test_schema_snapshot_view_names(self):
        """Test view_names property."""
        view1 = ViewMetadata(
            name="customers_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        view2 = ViewMetadata(
            name="orders_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        snapshot = SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"customers_view": view1, "orders_view": view2},
        )
        assert set(snapshot.view_names) == {"customers_view", "orders_view"}

    def test_schema_snapshot_total_columns(self):
        """Test total_columns property."""
        view1 = ViewMetadata(
            name="customers_view",
            columns=[
                ColumnMetadata(name="id", data_type="integer"),
                ColumnMetadata(name="name", data_type="varchar"),
            ],
        )
        view2 = ViewMetadata(
            name="orders_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        snapshot = SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"customers_view": view1, "orders_view": view2},
        )
        assert snapshot.total_columns == 3

    def test_schema_snapshot_to_dict(self):
        """Test conversion to dict."""
        view = ViewMetadata(
            name="customers_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        snapshot = SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"customers_view": view},
            constraints={"max_rows": 10000},
        )
        d = snapshot.to_dict()
        assert d["tenant_id"] == "tenant1"
        assert d["role"] == "analyst"
        assert "customers_view" in d["views"]
        assert d["constraints"]["max_rows"] == 10000

    def test_schema_snapshot_to_json(self):
        """Test conversion to JSON string."""
        view = ViewMetadata(
            name="customers_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        snapshot = SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"customers_view": view},
        )
        json_str = snapshot.to_json()
        data = json.loads(json_str)
        assert data["tenant_id"] == "tenant1"
        assert "customers_view" in data["views"]


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_cache_entry_not_expired(self):
        """Test cache entry that is not expired."""
        view = ViewMetadata(
            name="test_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        snapshot = SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"test_view": view},
        )
        entry = CacheEntry(
            snapshot=snapshot,
            cached_at=datetime.utcnow(),
            ttl_seconds=3600,
        )
        assert entry.is_expired() is False
        assert entry.age_seconds() < 10

    def test_cache_entry_expired(self):
        """Test cache entry that is expired."""
        view = ViewMetadata(
            name="test_view",
            columns=[ColumnMetadata(name="id", data_type="integer")],
        )
        snapshot = SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"test_view": view},
        )
        old_time = datetime.utcnow() - timedelta(seconds=7200)  # 2 hours ago
        entry = CacheEntry(
            snapshot=snapshot,
            cached_at=old_time,
            ttl_seconds=3600,  # 1 hour TTL
        )
        assert entry.is_expired() is True
        assert entry.age_seconds() > 7000


class TestSchemaSnapshotGenerator:
    """Tests for SchemaSnapshotGenerator."""

    @pytest.fixture
    def mock_allowlist_config(self):
        """Create mock allowlist config for testing."""
        analyst_role = RoleConfig(
            views=["customers_view", "data_sources_summary_view"],
            columns={
                "customers_view": ["id", "nome", "created_at"],
                "data_sources_summary_view": ["id", "tipo_fonte", "caminho"],
            },
            aggregates=["COUNT", "SUM", "AVG"],
            max_rows=10000,
            max_execution_time_seconds=30,
            join_paths=[
                JoinPath(
                    from_view="customers_view",
                    to_view="data_sources_summary_view",
                    on="cliente_vizu_id",
                    allowed=True,
                )
            ],
        )
        viewer_role = RoleConfig(
            views=["customers_view"],
            columns={"customers_view": ["id", "nome"]},
            aggregates=["COUNT"],
            max_rows=1000,
            max_execution_time_seconds=15,
        )
        admin_role = RoleConfig(
            views=[
                "customers_view",
                "data_sources_summary_view",
                "service_credentials_list_view",
                "tenant_config_view",
            ],
            columns={
                "customers_view": ["*"],
                "data_sources_summary_view": ["*"],
                "service_credentials_list_view": ["*"],
                "tenant_config_view": ["*"],
            },
            aggregates=["COUNT", "SUM", "AVG", "MIN", "MAX"],
            max_rows=100000,
            max_execution_time_seconds=60,
        )

        tenant1 = TenantConfig(
            name="Test Tenant 1",
            roles={
                "analyst": analyst_role,
                "viewer": viewer_role,
                "admin": admin_role,
            },
        )
        tenant2 = TenantConfig(
            name="Test Tenant 2",
            roles={
                "analyst": analyst_role,
                "viewer": viewer_role,
            },
        )

        return AllowlistConfig(
            version="1.0.0",
            description="Test allowlist",
            tenants={
                "tenant1": tenant1,
                "tenant2": tenant2,
            },
        )

    def test_generator_initialization(self, mock_allowlist_config):
        """Test generator initialization."""
        gen = SchemaSnapshotGenerator(
            allowlist_config=mock_allowlist_config,
            cache_ttl_seconds=1800,
        )
        assert gen.cache_ttl_seconds == 1800
        assert gen.allowlist_config is mock_allowlist_config

    def test_generate_valid_snapshot(self, mock_allowlist_config):
        """Test generating valid snapshot."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        snapshot = gen.generate("tenant1", "analyst")

        assert snapshot is not None
        assert snapshot.tenant_id == "tenant1"
        assert snapshot.role == "analyst"
        # Analyst should see customers and data_sources views
        assert "customers_view" in snapshot.views
        assert "data_sources_summary_view" in snapshot.views
        # But not service_credentials_list_view (admin only)
        assert "service_credentials_list_view" not in snapshot.views

    def test_generate_invalid_tenant(self, mock_allowlist_config):
        """Test generating snapshot for invalid tenant."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        snapshot = gen.generate("unknown_tenant", "analyst")
        assert snapshot is None

    def test_generate_invalid_role(self, mock_allowlist_config):
        """Test generating snapshot for invalid role."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        with pytest.raises(ValueError):
            gen.generate("tenant1", "invalid_role")

    def test_generate_caching(self, mock_allowlist_config):
        """Test that snapshots are cached."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        snapshot1 = gen.generate("tenant1", "analyst")
        snapshot2 = gen.generate("tenant1", "analyst")

        # Should return same object (cached)
        assert snapshot1 is snapshot2

    def test_generate_cache_expiry(self, mock_allowlist_config):
        """Test cache expiry with short TTL."""
        gen = SchemaSnapshotGenerator(
            allowlist_config=mock_allowlist_config,
            cache_ttl_seconds=1,  # 1 second TTL
        )
        snapshot1 = gen.generate("tenant1", "analyst")

        # Simulate cache expiry by manipulating cache
        cache_key = gen._cache_key("tenant1", "analyst")
        entry = gen._cache[cache_key]
        entry.cached_at = datetime.utcnow() - timedelta(seconds=2)  # Aged 2 seconds

        # Should regenerate (new object)
        snapshot2 = gen.generate("tenant1", "analyst")
        assert snapshot1 is not snapshot2

    def test_generate_force_refresh(self, mock_allowlist_config):
        """Test force refresh bypasses cache."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        snapshot1 = gen.generate("tenant1", "analyst")
        snapshot2 = gen.generate("tenant1", "analyst", force_refresh=True)

        # Force refresh should create new object
        assert snapshot1 is not snapshot2

    def test_filter_columns_by_role(self, mock_allowlist_config):
        """Test that columns are filtered by role."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)

        analyst_snapshot = gen.generate("tenant1", "analyst")
        viewer_snapshot = gen.generate("tenant1", "viewer")

        # Analyst has more columns
        analyst_cols = {col.name for col in analyst_snapshot.views["customers_view"].columns}
        viewer_cols = {col.name for col in viewer_snapshot.views["customers_view"].columns}

        assert "created_at" in analyst_cols
        assert "created_at" not in viewer_cols
        assert "id" in analyst_cols
        assert "id" in viewer_cols
        assert "nome" in analyst_cols
        assert "nome" in viewer_cols

    def test_admin_has_all_views(self, mock_allowlist_config):
        """Test that admin role has access to all views."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        admin_snapshot = gen.generate("tenant1", "admin")

        # Admin should see all views
        assert "customers_view" in admin_snapshot.views
        assert "data_sources_summary_view" in admin_snapshot.views
        assert "service_credentials_list_view" in admin_snapshot.views
        assert "tenant_config_view" in admin_snapshot.views

    def test_cache_info(self, mock_allowlist_config):
        """Test cache_info method."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        gen.generate("tenant1", "analyst")
        gen.generate("tenant1", "viewer")

        info = gen.cache_info()
        assert info["entries"] == 2
        assert info["ttl_seconds"] == gen.cache_ttl_seconds
        assert len(info["cached_keys"]) == 2

    def test_clear_cache_all(self, mock_allowlist_config):
        """Test clearing entire cache."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        gen.generate("tenant1", "analyst")
        gen.generate("tenant1", "viewer")
        gen.generate("tenant2", "analyst")

        cleared = gen.clear_cache()
        assert cleared == 3
        assert len(gen._cache) == 0

    def test_clear_cache_by_tenant(self, mock_allowlist_config):
        """Test clearing cache by tenant."""
        gen = SchemaSnapshotGenerator(allowlist_config=mock_allowlist_config)
        gen.generate("tenant1", "analyst")
        gen.generate("tenant1", "viewer")
        gen.generate("tenant2", "analyst")

        cleared = gen.clear_cache("tenant1")
        assert cleared == 2
        assert len(gen._cache) == 1


class TestSchemaSnapshotFormatter:
    """Tests for SchemaSnapshotFormatter."""

    @pytest.fixture
    def sample_snapshot(self):
        """Create sample snapshot for formatting tests."""
        cols = [
            ColumnMetadata(name="id", data_type="integer", is_primary_key=True),
            ColumnMetadata(name="name", data_type="varchar"),
            ColumnMetadata(name="created_at", data_type="timestamp"),
        ]
        view = ViewMetadata(
            name="customers_view",
            columns=cols,
            description="Customer records",
        )
        return SchemaSnapshot(
            tenant_id="tenant1",
            role="analyst",
            views={"customers_view": view},
            constraints={
                "max_rows": 10000,
                "max_execution_time_seconds": 30,
                "allowed_aggregates": ["COUNT", "SUM"],
            },
            join_paths=[],
        )

    def test_format_for_prompt(self, sample_snapshot):
        """Test formatting for LLM prompt."""
        formatted = SchemaSnapshotFormatter.format_for_prompt(sample_snapshot)

        assert "tenant1" in formatted
        assert "analyst" in formatted
        assert "customers_view" in formatted
        assert "id" in formatted
        assert "varchar" in formatted
        assert "Max rows per query: 10000" in formatted

    def test_format_as_json(self, sample_snapshot):
        """Test formatting as JSON."""
        json_str = SchemaSnapshotFormatter.format_as_json(sample_snapshot)
        data = json.loads(json_str)

        assert data["tenant_id"] == "tenant1"
        assert data["role"] == "analyst"
        assert "customers_view" in data["views"]
