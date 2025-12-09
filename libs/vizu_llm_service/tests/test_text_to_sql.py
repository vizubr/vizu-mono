"""
Tests for TextToSqlPrompt wrapper (Phase 1 Refactoring).

Tests the simplified TextToSqlPrompt class that leverages
vizu_prompt_management infrastructure (PromptLoader, VariableExtractor,
ContextVariableBuilder).

This replaces the old TextToSqlPromptBuilder with a thin wrapper
that uses existing template management and variable extraction.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID

from vizu_llm_service.text_to_sql import (
    TextToSqlPrompt,
    get_text_to_sql_prompt,
)
from vizu_prompt_management.loader import PromptLoader
from vizu_prompt_management.variables import (
    VariableExtractor,
    ContextVariableBuilder,
)
from vizu_models.context import VizuClientContext


@pytest.fixture
def mock_prompt_loader():
    """Create mock PromptLoader."""
    loader = AsyncMock(spec=PromptLoader)
    # Mock load response
    loaded = Mock()
    loaded.content = (
        "SELECT COUNT(*) AS total_records "
        "FROM customers_view "
        "WHERE client_id = 'tenant-123' "
        "LIMIT 100"
    )
    loader.load.return_value = loaded
    return loader


@pytest.fixture
def mock_context():
    """Create mock VizuClientContext."""
    context = Mock(spec=VizuClientContext)
    context.cliente_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    context.user_role = "analyst"
    context.tenant_name = "Acme Corp"
    context.empresa_id = UUID("660e8400-e29b-41d4-a716-446655440001")
    return context


class TestTextToSqlPrompt:
    """Test TextToSqlPrompt wrapper class."""

    def test_init_with_loader(self, mock_prompt_loader):
        """Test initialization with provided loader."""
        prompt = TextToSqlPrompt(prompt_loader=mock_prompt_loader)
        assert prompt.loader == mock_prompt_loader

    def test_init_without_loader(self):
        """Test initialization without loader (creates default)."""
        prompt = TextToSqlPrompt()
        assert prompt.loader is not None
        assert isinstance(prompt.loader, PromptLoader)

    @pytest.mark.asyncio
    async def test_build_with_all_params(self, mock_prompt_loader):
        """Test build() with all parameters."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Call build
        result = await prompt_obj.build(
            question="How many customers do we have?",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            role="analyst",
            schema_snapshot={
                "tables": {
                    "customers_view": {
                        "columns": ["id", "name", "client_id"]
                    }
                }
            },
            role_config={
                "allowed_views": ["customers_view"],
                "allowed_columns": ["id", "name", "client_id"],
                "max_rows": 100,
            },
        )

        # Verify loader was called
        assert mock_prompt_loader.load.called
        call_kwargs = mock_prompt_loader.load.call_args[1]

        # Check variables were passed
        assert "variables" in call_kwargs
        variables = call_kwargs["variables"]
        assert variables["question"] == "How many customers do we have?"
        assert variables["tenant_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert variables["user_role"] == "analyst"

        # Check result
        assert result is not None
        assert "COUNT(*)" in result or "total_records" in result

    @pytest.mark.asyncio
    async def test_build_from_context(self, mock_prompt_loader, mock_context):
        """Test build_from_context() with VizuClientContext."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Call build_from_context
        result = await prompt_obj.build_from_context(
            question="List all active customers",
            context=mock_context,
            schema_snapshot={
                "tables": {
                    "customers_view": {
                        "columns": ["id", "name", "status"]
                    }
                }
            },
        )

        # Verify loader was called
        assert mock_prompt_loader.load.called
        call_kwargs = mock_prompt_loader.load.call_args[1]

        # Check context was extracted
        variables = call_kwargs["variables"]
        assert variables["cliente_id"] == str(mock_context.cliente_id)
        assert variables["user_role"] == "analyst"
        assert variables["question"] == "List all active customers"

        # Check result
        assert result is not None

    @pytest.mark.asyncio
    async def test_build_with_optional_exemplars(self, mock_prompt_loader):
        """Test build() with optional exemplars."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        exemplars = [
            {
                "question": "Count of records",
                "sql": "SELECT COUNT(*) FROM table WHERE client_id = :client_id"
            }
        ]

        result = await prompt_obj.build(
            question="Get count of records",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            role="analyst",
            schema_snapshot={},
            role_config={},
            exemplars=exemplars,
        )

        # Verify loader was called with exemplars
        assert mock_prompt_loader.load.called
        call_kwargs = mock_prompt_loader.load.call_args[1]
        variables = call_kwargs["variables"]
        assert "exemplars" in variables
        assert variables["exemplars"] == exemplars

    @pytest.mark.asyncio
    async def test_build_without_schema(self, mock_prompt_loader):
        """Test build() without schema_snapshot."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        result = await prompt_obj.build(
            question="Simple question",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            role="viewer",
            schema_snapshot=None,
            role_config=None,
        )

        # Should still work with None schema
        assert mock_prompt_loader.load.called
        assert result is not None

    @pytest.mark.asyncio
    async def test_format_schema_summary(self, mock_prompt_loader):
        """Test _format_schema() creates proper summary."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        schema = {
            "tables": {
                "customers": {"columns": ["id", "name"]},
                "orders": {"columns": ["id", "customer_id", "amount"]},
            }
        }

        summary = prompt_obj._format_schema(schema)

        # Should create readable summary
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "customers" in summary
        assert "orders" in summary

    def test_format_views_list(self, mock_prompt_loader):
        """Test _format_views() creates proper list."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        allowed_views = [
            "customers_view",
            "orders_view",
            "analytics_summary",
        ]

        formatted = prompt_obj._format_views(allowed_views)

        assert isinstance(formatted, str)
        assert "customers_view" in formatted
        assert "orders_view" in formatted

    def test_format_columns_list(self, mock_prompt_loader):
        """Test _format_columns() creates proper list."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        allowed_columns = [
            "id",
            "name",
            "email",
            "created_at",
        ]

        formatted = prompt_obj._format_columns(allowed_columns)

        assert isinstance(formatted, str)
        assert "id" in formatted
        assert "name" in formatted

    def test_get_text_to_sql_prompt_singleton(self):
        """Test get_text_to_sql_prompt() returns singleton."""
        prompt1 = get_text_to_sql_prompt()
        prompt2 = get_text_to_sql_prompt()

        # Should be same instance
        assert prompt1 is prompt2

    def test_get_text_to_sql_prompt_with_loader(self, mock_prompt_loader):
        """Test get_text_to_sql_prompt() with custom loader."""
        # Note: singleton factory, so this creates new instance if loader provided
        prompt = get_text_to_sql_prompt(loader=mock_prompt_loader)

        assert prompt is not None
        assert isinstance(prompt, TextToSqlPrompt)


class TestTextToSqlPromptIntegration:
    """Integration tests with vizu_prompt_management."""

    @pytest.mark.asyncio
    async def test_uses_prompt_loader(self):
        """Verify TextToSqlPrompt actually uses PromptLoader."""
        # Create with real PromptLoader (mocked at template level)
        with patch("vizu_prompt_management.loader.PromptLoader.load") as mock_load:
            mock_template = Mock()
            mock_template.content = "SELECT 1"
            mock_load.return_value = mock_template

            prompt_obj = TextToSqlPrompt()

            await prompt_obj.build(
                question="Test",
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                role="analyst",
            )

            # Should have called PromptLoader.load
            assert mock_load.called

    @pytest.mark.asyncio
    async def test_integrates_with_context_builder(self, mock_prompt_loader):
        """Verify TextToSqlPrompt uses ContextVariableBuilder."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # This should use ContextVariableBuilder internally
        await prompt_obj.build(
            question="Test question",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            role="admin",
        )

        # Check that variables were built properly
        call_kwargs = mock_prompt_loader.load.call_args[1]
        variables = call_kwargs["variables"]

        # Should have expected keys from builder
        assert "cliente_id" in variables
        assert "tenant_id" in variables
        assert "user_role" in variables
        assert "question" in variables


class TestTextToSqlPromptEdgeCases:
    """Edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_build_with_empty_schema(self, mock_prompt_loader):
        """Test build() with empty schema."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        result = await prompt_obj.build(
            question="Query",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            role="analyst",
            schema_snapshot={},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_build_with_large_schema(self, mock_prompt_loader):
        """Test build() with large schema."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Create large schema
        large_schema = {
            "tables": {
                f"table_{i}": {
                    "columns": [f"col_{j}" for j in range(10)]
                }
                for i in range(50)
            }
        }

        result = await prompt_obj.build(
            question="Count records",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            role="analyst",
            schema_snapshot=large_schema,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_build_with_special_characters_in_question(self, mock_prompt_loader):
        """Test build() with special characters in question."""
        prompt_obj = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        result = await prompt_obj.build(
            question="What's the count of 'active' users & pending orders?",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            role="analyst",
        )

        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
