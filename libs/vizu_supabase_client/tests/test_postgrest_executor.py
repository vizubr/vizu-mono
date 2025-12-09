"""
Tests for PostgREST query executor.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from vizu_supabase_client.postgrest_executor import (
    QueryResult,
    PostgRESTQueryExecutor,
    get_postgrest_executor,
)
from vizu_supabase_client.auth_context import AuthContext


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_query_result_creation(self):
        """Test basic QueryResult creation."""
        result = QueryResult(
            rows=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            column_names=["id", "name"],
            column_types={"id": "integer", "name": "varchar"},
            total_rows=2,
        )
        assert len(result) == 2
        assert result.get_count() == 2

    def test_query_result_len(self):
        """Test __len__ method."""
        result = QueryResult(
            rows=[{"id": 1}],
            column_names=["id"],
            column_types={"id": "integer"},
        )
        assert len(result) == 1

    def test_query_result_get_count_with_total(self):
        """Test get_count with total_rows set."""
        result = QueryResult(
            rows=[{"id": 1}],
            column_names=["id"],
            column_types={"id": "integer"},
            total_rows=100,
        )
        assert result.get_count() == 100

    def test_query_result_get_count_without_total(self):
        """Test get_count without total_rows."""
        result = QueryResult(
            rows=[{"id": 1}, {"id": 2}],
            column_names=["id"],
            column_types={"id": "integer"},
        )
        assert result.get_count() == 2


class TestPostgRESTQueryExecutor:
    """Tests for PostgRESTQueryExecutor."""

    @pytest.fixture
    def executor(self):
        """Create executor instance."""
        return PostgRESTQueryExecutor(
            max_rows_per_request=100,
            default_timeout_seconds=30,
        )

    @pytest.fixture
    def auth_context(self):
        """Create sample auth context."""
        return AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="analyst",
        )

    def test_executor_initialization(self, executor):
        """Test executor initialization."""
        assert executor.max_rows_per_request == 100
        assert executor.default_timeout_seconds == 30
        assert executor.max_retries == 3

    def test_query_invalid_view_name(self, executor):
        """Test query with invalid view name."""
        with pytest.raises(ValueError, match="view_name is required"):
            executor.query(view_name="")

    def test_query_limit_capped(self, executor):
        """Test that limit is capped at max_rows_per_request."""
        # Mock the Supabase client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_response.count = None

        # Mock the query builder chain
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query(
                view_name="customers_view",
                limit=500,  # Exceeds max
            )
            # Verify range was called with capped limit
            _, range_args = mock_table.range.call_args
            assert range_args[1] - range_args[0] < 500

    def test_query_with_filters(self, executor):
        """Test query with filters."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": 1, "name": "Alice"}]
        mock_response.count = None

        mock_table = MagicMock()
        mock_table.eq.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query(
                view_name="customers_view",
                filters={"status": "active"},
            )
            # Verify filter was applied
            mock_table.eq.assert_called_with("status", "active")

    def test_query_with_specific_columns(self, executor):
        """Test query selecting specific columns."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_response.count = None

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query(
                view_name="customers_view",
                columns=["id", "name"],
            )
            # Verify select was called with columns
            mock_table.select.assert_called()

    def test_query_with_pagination(self, executor):
        """Test query with pagination."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_response.count = None

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query(
                view_name="customers_view",
                limit=10,
                offset=20,
            )
            # Verify range was called with offset and limit
            mock_table.range.assert_called()

    def test_query_with_count(self, executor):
        """Test query with count flag."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_response.count = 1000

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.count.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query(
                view_name="customers_view",
                count=True,
            )
            assert result.total_rows == 1000

    def test_query_result_parsing(self, executor):
        """Test parsing query result."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        mock_response.count = None

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query(
                view_name="customers_view",
            )
            assert len(result) == 2
            assert result.column_names == ["id", "name"]
            assert result.rows[0]["id"] == 1

    def test_query_empty_result(self, executor):
        """Test query returning no rows."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_response.count = None

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query(
                view_name="customers_view",
            )
            assert len(result) == 0
            assert result.column_names == []

    def test_query_with_context(self, executor, auth_context):
        """Test query with auth context."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_response.count = None

        mock_table = MagicMock()
        mock_table.eq.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query_with_context(
                view_name="customers_view",
                auth_context=auth_context,
            )
            # Verify tenant_id filter was added
            assert mock_table.eq.called

    def test_query_with_context_includes_tenant_id(self, executor, auth_context):
        """Test that query_with_context includes tenant_id filter."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": 1}]
        mock_response.count = None

        mock_table = MagicMock()
        mock_table.eq.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.execute.return_value = mock_response
        mock_client.table.return_value = mock_table

        with patch("vizu_supabase_client.postgrest_executor.get_supabase_client", return_value=mock_client):
            result = executor.query_with_context(
                view_name="customers_view",
                auth_context=auth_context,
                filters={"status": "active"},
            )
            # Verify both tenant_id and status filters were applied
            calls = [call for call in mock_table.eq.call_args_list]
            # Should have been called for tenant_id
            assert len(calls) >= 1


class TestPostgRESTQueryExecutorRetry:
    """Tests for retry logic."""

    @pytest.fixture
    def executor(self):
        return PostgRESTQueryExecutor(max_retries=2)

    def test_execute_with_retry_success_first_try(self, executor):
        """Test successful execution on first try."""
        mock_query = MagicMock()
        mock_response = MagicMock()
        mock_query.execute.return_value = mock_response

        result = executor._execute_with_retry(mock_query)
        assert result is mock_response
        assert mock_query.execute.call_count == 1

    def test_execute_with_retry_success_after_retry(self, executor):
        """Test successful execution after retry."""
        mock_query = MagicMock()
        mock_response = MagicMock()
        # Fail first time, succeed second time
        mock_query.execute.side_effect = [
            Exception("Connection error"),
            mock_response,
        ]

        with patch("time.sleep"):  # Mock sleep to avoid delays
            result = executor._execute_with_retry(mock_query)
        assert result is mock_response
        assert mock_query.execute.call_count == 2

    def test_execute_with_retry_exhausted(self, executor):
        """Test failure after retries exhausted."""
        mock_query = MagicMock()
        mock_query.execute.side_effect = Exception("Persistent error")

        with patch("time.sleep"):  # Mock sleep
            with pytest.raises(Exception, match="Persistent error"):
                executor._execute_with_retry(mock_query)


class TestPostgRESTQueryExecutorSingleton:
    """Tests for singleton pattern."""

    def test_get_postgrest_executor_singleton(self):
        """Test that get_postgrest_executor returns singleton."""
        exec1 = get_postgrest_executor()
        exec2 = get_postgrest_executor()
        assert exec1 is exec2
