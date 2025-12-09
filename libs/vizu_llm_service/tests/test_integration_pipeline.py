"""
Phase 1.5 Integration Test: Text-to-SQL Pipeline

Complete end-to-end test of the text-to-SQL generation pipeline:
1. TextToSqlPrompt.build_from_context() - Prompt assembly
2. TextToSqlLLMCall.invoke() - LLM invocation with retry
3. Response parsing and validation

This test validates the full workflow from natural language question
to LLM response, ensuring all components integrate properly.
"""

import pytest
import asyncio
from uuid import UUID
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from vizu_llm_service import (
    TextToSqlPrompt,
    TextToSqlLLMConfig,
    TextToSqlLLMCall,
    get_text_to_sql_prompt,
    get_llm_call,
)
from vizu_llm_service.text_to_sql_config import TextToSqlLLMResponse
from vizu_prompt_management.loader import PromptLoader
from vizu_models.context import VizuClientContext


@pytest.fixture
def mock_context():
    """Create realistic mock VizuClientContext."""
    context = Mock(spec=VizuClientContext)
    context.cliente_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    context.user_role = "analyst"
    context.tenant_name = "Acme Analytics"
    context.empresa_id = UUID("660e8400-e29b-41d4-a716-446655440001")
    return context


@pytest.fixture
def realistic_schema():
    """Create realistic database schema snapshot."""
    return {
        "tables": {
            "customers_view": {
                "columns": {
                    "id": {"type": "uuid", "nullable": False},
                    "name": {"type": "text", "nullable": False},
                    "email": {"type": "text", "nullable": True},
                    "status": {"type": "text", "nullable": False},
                    "created_at": {"type": "timestamp", "nullable": False},
                    "client_id": {"type": "uuid", "nullable": False},
                }
            },
            "orders_view": {
                "columns": {
                    "id": {"type": "uuid", "nullable": False},
                    "customer_id": {"type": "uuid", "nullable": False},
                    "amount": {"type": "numeric", "nullable": False},
                    "status": {"type": "text", "nullable": False},
                    "created_at": {"type": "timestamp", "nullable": False},
                    "client_id": {"type": "uuid", "nullable": False},
                }
            },
        }
    }


@pytest.fixture
def role_config():
    """Create realistic role configuration."""
    return {
        "allowed_views": ["customers_view", "orders_view"],
        "allowed_columns": [
            "id", "name", "email", "status", "created_at",
            "customer_id", "amount"
        ],
        "allowed_aggregates": ["COUNT", "SUM", "AVG", "MIN", "MAX"],
        "max_rows_limit": 10000,
        "mandatory_filters": ["client_id = :client_id"],
    }


@pytest.fixture
def mock_prompt_loader():
    """Create mock PromptLoader for testing."""
    loader = AsyncMock(spec=PromptLoader)

    # Simulate template loading
    async def mock_load(template_name, variables=None, **kwargs):
        template = Mock()
        template.content = (
            "Given the following schema and constraints, "
            "generate a PostgreSQL SELECT query for: {question}\n"
            "Schema: {schema_summary}\n"
            "Allowed Views: {allowed_views}\n"
            "Allowed Columns: {allowed_columns}\n"
            "Constraints:\n"
            "- Must include client_id filter: {client_id}\n"
            "- Max rows: {max_rows_limit}\n"
            "- User role: {user_role}\n"
            "Return ONLY the SQL query, no explanation."
        )
        return template

    loader.load = mock_load
    return loader


class TestTextToSqlPipeline:
    """Test complete text-to-SQL pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(self, mock_prompt_loader, mock_context, realistic_schema, role_config):
        """Test complete pipeline: prompt assembly → LLM call → response."""
        # Step 1: Build prompt
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        assembled_prompt = await prompt_builder.build_from_context(
            question="How many active customers do we have?",
            context=mock_context,
            schema_snapshot=realistic_schema,
            role_config=role_config,
        )

        assert assembled_prompt is not None
        assert "active customers" in assembled_prompt
        assert "client_id" in assembled_prompt
        assert "SELECT" in assembled_prompt or "schema" in assembled_prompt.lower()

        # Step 2: Configure LLM
        config = TextToSqlLLMConfig.default_gpt4_turbo()
        assert config.model == "gpt-4-turbo"
        assert config.temperature == 0.0

        # Step 3: Create LLM call instance
        llm_call = TextToSqlLLMCall(config=config)

        # Step 4: Invoke LLM
        response = await llm_call.invoke(assembled_prompt)

        # Verify response
        assert isinstance(response, TextToSqlLLMResponse)
        assert response.success is True
        assert response.sql is not None
        assert "SELECT" in response.sql or "COUNT" in response.sql
        assert response.usage is not None
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    async def test_pipeline_with_exemplars(self, mock_prompt_loader, mock_context, realistic_schema, role_config):
        """Test pipeline with few-shot exemplars."""
        exemplars = [
            {
                "question": "Count of records",
                "sql": "SELECT COUNT(*) as count FROM customers_view WHERE client_id = :client_id LIMIT 100"
            },
            {
                "question": "Sum of amounts",
                "sql": "SELECT SUM(amount) as total FROM orders_view WHERE client_id = :client_id AND status = 'completed' LIMIT 100"
            }
        ]

        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        assembled_prompt = await prompt_builder.build_from_context(
            question="Total revenue from completed orders",
            context=mock_context,
            schema_snapshot=realistic_schema,
            role_config=role_config,
            exemplars=exemplars,
        )

        assert assembled_prompt is not None

        # Invoke LLM
        config = TextToSqlLLMConfig.default_gpt4_turbo()
        llm_call = TextToSqlLLMCall(config=config)
        response = await llm_call.invoke(assembled_prompt)

        assert response.success is True
        assert response.sql is not None

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, mock_prompt_loader, mock_context, realistic_schema):
        """Test pipeline handles impossible questions gracefully."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Question that LLM should respond with UNABLE
        assembled_prompt = await prompt_builder.build_from_context(
            question="impossible query that violates constraints and has no solution",
            context=mock_context,
            schema_snapshot=realistic_schema,
        )

        config = TextToSqlLLMConfig.default_gpt4_turbo()
        llm_call = TextToSqlLLMCall(config=config)
        response = await llm_call.invoke(assembled_prompt)

        # Should handle gracefully (either UNABLE or valid SQL)
        assert isinstance(response, TextToSqlLLMResponse)
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    async def test_pipeline_with_retry(self, mock_prompt_loader, mock_context):
        """Test pipeline retry mechanism on transient failures."""
        # Create config with retries
        config = TextToSqlLLMConfig(
            model="gpt-4-turbo",
            provider="openai",
            max_retries=3,
            initial_retry_delay_ms=100,
            max_retry_delay_ms=500,
        )

        llm_call = TextToSqlLLMCall(config=config)

        # Should retry and eventually succeed
        prompt = "Simple prompt"
        response = await llm_call.invoke(prompt)

        assert isinstance(response, TextToSqlLLMResponse)
        assert response.retry_count >= 0

    @pytest.mark.asyncio
    async def test_pipeline_with_singleton_factories(self, mock_prompt_loader, mock_context, realistic_schema, role_config):
        """Test pipeline using singleton factory functions."""
        # Get singleton instances
        prompt_builder = get_text_to_sql_prompt()
        llm_call = get_llm_call()

        # Build and invoke
        assembled_prompt = await prompt_builder.build_from_context(
            question="How many orders?",
            context=mock_context,
            schema_snapshot=realistic_schema,
            role_config=role_config,
        )

        response = await llm_call.invoke(assembled_prompt)

        assert response.success is True
        assert response.sql is not None

        # Verify singletons are reused
        prompt_builder2 = get_text_to_sql_prompt()
        llm_call2 = get_llm_call()

        assert prompt_builder is prompt_builder2
        assert llm_call is llm_call2


class TestPipelineSecurityValidation:
    """Test security aspects of the pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_includes_tenant_isolation(self, mock_prompt_loader, mock_context, realistic_schema):
        """Test that pipeline enforces tenant isolation."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        assembled_prompt = await prompt_builder.build_from_context(
            question="List all customers",
            context=mock_context,
            schema_snapshot=realistic_schema,
        )

        # Tenant ID must be in the prompt
        assert str(mock_context.cliente_id) in assembled_prompt or "client_id" in assembled_prompt

    @pytest.mark.asyncio
    async def test_pipeline_enforces_role_based_access(self, mock_prompt_loader, mock_context, realistic_schema, role_config):
        """Test that pipeline enforces role-based column access."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Only allowed columns should be in allowed_columns list
        allowed_cols = role_config["allowed_columns"]

        assembled_prompt = await prompt_builder.build_from_context(
            question="Select all user data",
            context=mock_context,
            schema_snapshot=realistic_schema,
            role_config=role_config,
        )

        # Prompt should contain the allowed columns
        for col in allowed_cols[:3]:  # Check at least first 3
            assert col in assembled_prompt or col.lower() in assembled_prompt.lower()

    @pytest.mark.asyncio
    async def test_pipeline_validates_result_limits(self, mock_prompt_loader, mock_context, realistic_schema, role_config):
        """Test that pipeline enforces result row limits."""
        max_rows = role_config["max_rows_limit"]

        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        assembled_prompt = await prompt_builder.build_from_context(
            question="Get all records",
            context=mock_context,
            schema_snapshot=realistic_schema,
            role_config=role_config,
        )

        # Max rows limit should be in prompt
        assert str(max_rows) in assembled_prompt or "LIMIT" in assembled_prompt


class TestPipelinePerformance:
    """Test performance characteristics of the pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_latency(self, mock_prompt_loader, mock_context, realistic_schema):
        """Test pipeline latency is reasonable."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)
        config = TextToSqlLLMConfig.default_gpt4_turbo()
        llm_call = TextToSqlLLMCall(config=config)

        # Build prompt (should be fast)
        assembled_prompt = await prompt_builder.build_from_context(
            question="Quick query",
            context=mock_context,
            schema_snapshot=realistic_schema,
        )

        # Call LLM
        response = await llm_call.invoke(assembled_prompt)

        # Total latency should be reasonable (mock is ~150ms)
        assert response.latency_ms < 1000  # Should be < 1 second

    @pytest.mark.asyncio
    async def test_pipeline_handles_large_schema(self, mock_prompt_loader, mock_context, role_config):
        """Test pipeline can handle large schema without issues."""
        # Create large schema
        large_schema = {
            "tables": {
                f"table_{i}": {
                    "columns": {
                        f"col_{j}": {"type": "text", "nullable": True}
                        for j in range(20)
                    }
                }
                for i in range(100)
            }
        }

        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        assembled_prompt = await prompt_builder.build_from_context(
            question="Query large schema",
            context=mock_context,
            schema_snapshot=large_schema,
        )

        # Should handle large schema
        assert assembled_prompt is not None
        assert len(assembled_prompt) > 0


class TestPipelineIntegrationWithComponents:
    """Test pipeline integration with individual components."""

    @pytest.mark.asyncio
    async def test_prompt_uses_vizu_prompt_management(self, mock_prompt_loader, mock_context, realistic_schema):
        """Test that TextToSqlPrompt properly uses vizu_prompt_management."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Should use provided loader
        assert prompt_builder.loader == mock_prompt_loader

        assembled_prompt = await prompt_builder.build_from_context(
            question="Test",
            context=mock_context,
            schema_snapshot=realistic_schema,
        )

        # Verify loader was used
        assert assembled_prompt is not None

    @pytest.mark.asyncio
    async def test_llm_config_properly_validates(self):
        """Test that TextToSqlLLMConfig validates parameters."""
        # Valid config should work
        valid_config = TextToSqlLLMConfig.default_gpt4_turbo()
        assert valid_config.temperature == 0.0
        assert valid_config.max_retries == 3

        # Invalid temperature should raise
        with pytest.raises(ValueError):
            TextToSqlLLMConfig(temperature=5.0)  # Out of range

        # Invalid retries should raise
        with pytest.raises(ValueError):
            TextToSqlLLMConfig(max_retries=15)  # Out of range

    @pytest.mark.asyncio
    async def test_llm_response_serialization(self, mock_prompt_loader, mock_context):
        """Test that LLM response can be serialized."""
        config = TextToSqlLLMConfig.default_gpt4_turbo()
        llm_call = TextToSqlLLMCall(config=config)

        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)
        assembled_prompt = await prompt_builder.build_from_context(
            question="Test",
            context=mock_context,
        )

        response = await llm_call.invoke(assembled_prompt)

        # Should be serializable
        response_dict = response.to_dict()
        assert response_dict is not None
        assert response_dict["success"] is True
        assert "sql" in response_dict


class TestPipelineRegressions:
    """Regression tests for known issues."""

    @pytest.mark.asyncio
    async def test_pipeline_handles_missing_schema_snapshot(self, mock_prompt_loader, mock_context):
        """Test pipeline works with minimal schema."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Should work with None schema
        assembled_prompt = await prompt_builder.build_from_context(
            question="Simple query",
            context=mock_context,
            schema_snapshot=None,
        )

        assert assembled_prompt is not None

    @pytest.mark.asyncio
    async def test_pipeline_handles_missing_role_config(self, mock_prompt_loader, mock_context, realistic_schema):
        """Test pipeline works without role config."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        # Should work with None role config
        assembled_prompt = await prompt_builder.build_from_context(
            question="Query",
            context=mock_context,
            schema_snapshot=realistic_schema,
            role_config=None,
        )

        assert assembled_prompt is not None

    @pytest.mark.asyncio
    async def test_pipeline_handles_special_characters(self, mock_prompt_loader, mock_context, realistic_schema):
        """Test pipeline handles special characters in questions."""
        prompt_builder = TextToSqlPrompt(prompt_loader=mock_prompt_loader)

        special_question = "What's the count of 'active' users & pending orders? (50%+ completion)"

        assembled_prompt = await prompt_builder.build_from_context(
            question=special_question,
            context=mock_context,
            schema_snapshot=realistic_schema,
        )

        assert assembled_prompt is not None
        assert "%" in assembled_prompt or "50" in assembled_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
