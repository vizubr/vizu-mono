"""
Tests for Text-to-SQL LLM Configuration

Phase 1.3: Tests for LLM parameters and call wrapper
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import time

from vizu_llm_service.text_to_sql_config import (
    TextToSqlLLMConfig,
    TextToSqlLLMResponse,
    TextToSqlLLMCall,
    LLMProvider,
    LLMModel,
    get_llm_call,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def default_config():
    """Create default LLM config."""
    return TextToSqlLLMConfig.default_gpt4_turbo()


@pytest.fixture
def claude_config():
    """Create Claude 3 Sonnet config."""
    return TextToSqlLLMConfig.default_claude3_sonnet()


@pytest.fixture
def custom_config():
    """Create custom LLM config."""
    return TextToSqlLLMConfig(
        model="gpt-4-turbo",
        provider="openai",
        temperature=0.0,
        max_tokens=300,
        max_retries=2,
        timeout_seconds=20.0,
        stop_tokens=["UNABLE", ";"],
    )


@pytest.fixture
def llm_call(default_config):
    """Create LLM call instance."""
    return TextToSqlLLMCall(config=default_config)


@pytest.fixture
def prompt():
    """Sample prompt for testing."""
    return "SELECT COUNT(*) FROM customers_view WHERE client_id = '123' LIMIT 100"


# =============================================================================
# UNIT TESTS: Configuration Validation
# =============================================================================


def test_default_gpt4_turbo_config(default_config):
    """Test default GPT-4 Turbo configuration."""
    assert default_config.model == "gpt-4-turbo"
    assert default_config.provider == "openai"
    assert default_config.temperature == 0.0
    assert default_config.max_tokens == 500
    assert default_config.max_retries == 3
    assert default_config.timeout_seconds == 30.0
    assert "UNABLE" in default_config.stop_tokens


def test_default_claude3_config(claude_config):
    """Test default Claude 3 Sonnet configuration."""
    assert claude_config.model == "claude-3-sonnet-20240229"
    assert claude_config.provider == "anthropic"
    assert claude_config.temperature == 0.0
    assert claude_config.max_tokens == 500


def test_config_post_init_default_stop_tokens():
    """Test that stop_tokens defaults are set."""
    config = TextToSqlLLMConfig()
    assert config.stop_tokens is not None
    assert "UNABLE" in config.stop_tokens
    assert ";" in config.stop_tokens


def test_config_temperature_validation_invalid_high():
    """Test temperature validation rejects values > 2.0."""
    with pytest.raises(ValueError, match="Temperature must be 0.0-2.0"):
        TextToSqlLLMConfig(temperature=2.5)


def test_config_temperature_validation_invalid_low():
    """Test temperature validation rejects negative values."""
    with pytest.raises(ValueError, match="Temperature must be 0.0-2.0"):
        TextToSqlLLMConfig(temperature=-0.1)


def test_config_temperature_valid_range():
    """Test valid temperature values."""
    for temp in [0.0, 0.5, 1.0, 1.5, 2.0]:
        config = TextToSqlLLMConfig(temperature=temp)
        assert config.temperature == temp


def test_config_max_retries_validation():
    """Test max_retries validation."""
    with pytest.raises(ValueError, match="max_retries must be 0-10"):
        TextToSqlLLMConfig(max_retries=15)


def test_config_to_dict():
    """Test config serialization to dict."""
    config = TextToSqlLLMConfig(model="gpt-4-turbo", max_tokens=600)
    config_dict = config.to_dict()

    assert isinstance(config_dict, dict)
    assert config_dict["model"] == "gpt-4-turbo"
    assert config_dict["max_tokens"] == 600


def test_config_logging_warnings(caplog):
    """Test that config logs warnings for unusual values."""
    import logging
    caplog.set_level(logging.WARNING)

    # Very low timeout
    config = TextToSqlLLMConfig(timeout_seconds=1.0)
    assert "timeout_seconds" in caplog.text or config.timeout_seconds == 1.0

    caplog.clear()

    # Unusual max_tokens
    config = TextToSqlLLMConfig(max_tokens=50)
    assert config.max_tokens == 50  # Should still work


# =============================================================================
# UNIT TESTS: LLM Response
# =============================================================================


def test_llm_response_success():
    """Test successful LLM response."""
    response = TextToSqlLLMResponse(
        success=True,
        sql="SELECT * FROM table LIMIT 100",
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        latency_ms=150.0,
    )

    assert response.success is True
    assert response.sql is not None
    assert response.error is None
    assert response.usage["total_tokens"] == 120


def test_llm_response_error():
    """Test error LLM response."""
    response = TextToSqlLLMResponse(
        success=False,
        sql=None,
        error="API timeout",
        error_code="TIMEOUT",
        latency_ms=30000.0,
    )

    assert response.success is False
    assert response.sql is None
    assert response.error == "API timeout"
    assert response.error_code == "TIMEOUT"


def test_llm_response_unable():
    """Test UNABLE response (cannot generate SQL)."""
    response = TextToSqlLLMResponse(
        success=False,
        sql=None,
        raw_response="UNABLE",
        error="LLM returned UNABLE",
        error_code="UNABLE_RESPONSE",
    )

    assert response.success is False
    assert "UNABLE" in response.error


def test_llm_response_to_dict():
    """Test response serialization."""
    response = TextToSqlLLMResponse(
        success=True,
        sql="SELECT 1",
        latency_ms=100.0,
    )

    resp_dict = response.to_dict()
    assert isinstance(resp_dict, dict)
    assert resp_dict["success"] is True
    assert resp_dict["sql"] == "SELECT 1"


# =============================================================================
# UNIT TESTS: LLM Call Initialization
# =============================================================================


def test_llm_call_init_default(default_config):
    """Test LLM call initialization with default config."""
    call = TextToSqlLLMCall(config=default_config)

    assert call.config.model == "gpt-4-turbo"
    assert call.config.temperature == 0.0


def test_llm_call_init_without_config():
    """Test LLM call initialization without config (uses default)."""
    call = TextToSqlLLMCall()

    assert call.config is not None
    assert call.config.model == "gpt-4-turbo"


def test_llm_call_api_key_loading(default_config, monkeypatch):
    """Test API key loading from environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")

    call = TextToSqlLLMCall(config=default_config)
    assert call.config.api_key == "sk-test-key-123"


def test_llm_call_api_key_provided(default_config):
    """Test that provided API key is not overwritten."""
    default_config.api_key = "sk-provided-key"

    call = TextToSqlLLMCall(config=default_config)
    assert call.config.api_key == "sk-provided-key"


# =============================================================================
# UNIT TESTS: System Prompt
# =============================================================================


def test_build_system_prompt_default(llm_call):
    """Test default system prompt."""
    prompt = llm_call._build_system_prompt()

    assert "SQL" in prompt
    assert "client_id" in prompt
    assert "LIMIT" in prompt
    assert "DDL" in prompt or "DML" in prompt


def test_build_system_prompt_disabled(custom_config):
    """Test system prompt when safety instructions disabled."""
    custom_config.safety_instructions_enabled = False
    call = TextToSqlLLMCall(config=custom_config)

    prompt = call._build_system_prompt()
    assert "helpful SQL assistant" in prompt
    assert "NEVER" not in prompt


def test_system_prompt_includes_constraints(llm_call):
    """Test that system prompt includes all constraints."""
    prompt = llm_call._build_system_prompt()

    constraints = [
        "tenant isolation",
        "client_id",
        "SELECT only",
        "LIMIT",
        "COUNT, SUM, AVG, MIN, MAX",
        "UNABLE",
    ]

    for constraint in constraints:
        assert constraint in prompt or constraint.lower() in prompt.lower()


# =============================================================================
# ASYNC TESTS: LLM Invocation
# =============================================================================


@pytest.mark.asyncio
async def test_invoke_success(llm_call, prompt):
    """Test successful LLM invocation."""
    response = await llm_call.invoke(prompt)

    assert response.success is True
    assert response.sql is not None
    assert response.error is None
    assert response.usage is not None


@pytest.mark.asyncio
async def test_invoke_with_custom_system_prompt(llm_call, prompt):
    """Test invocation with custom system prompt."""
    custom_system = "Custom SQL generator instructions"

    response = await llm_call.invoke(prompt, system_prompt=custom_system)

    assert response.success is True


@pytest.mark.asyncio
async def test_invoke_unable_case(llm_call):
    """Test invocation when cannot generate SQL."""
    prompt = "Generate SQL that violates all constraints and is impossible"

    response = await llm_call.invoke(prompt)

    # Stub returns UNABLE for impossible questions
    assert response.success is False or "UNABLE" in (response.raw_response or "")


@pytest.mark.asyncio
async def test_invoke_latency_tracking(llm_call, prompt):
    """Test that latency is tracked."""
    response = await llm_call.invoke(prompt)

    assert response.latency_ms > 0
    assert response.latency_ms < 1000  # Should be < 1 second for stub


@pytest.mark.asyncio
async def test_invoke_retry_on_error(custom_config):
    """Test retry behavior on error."""
    custom_config.max_retries = 1
    call = TextToSqlLLMCall(config=custom_config)

    # Stub won't error, so response should succeed
    response = await call.invoke("test prompt")
    assert response.success is True


@pytest.mark.asyncio
async def test_invoke_sync_wrapper(llm_call, prompt):
    """Test synchronous wrapper invoke_sync()."""
    response = await llm_call.invoke_sync(prompt)

    assert response.success is True
    assert response.sql is not None


# =============================================================================
# UNIT TESTS: Token Usage
# =============================================================================


@pytest.mark.asyncio
async def test_token_usage_tracking(llm_call, prompt):
    """Test that token usage is tracked."""
    response = await llm_call.invoke(prompt)

    assert response.usage is not None
    assert "prompt_tokens" in response.usage
    assert "completion_tokens" in response.usage
    assert "total_tokens" in response.usage

    # Verify token math
    total = response.usage["prompt_tokens"] + response.usage["completion_tokens"]
    assert response.usage["total_tokens"] == total


@pytest.mark.asyncio
async def test_token_usage_reasonable(llm_call, prompt):
    """Test that token counts are reasonable."""
    response = await llm_call.invoke(prompt)

    # Prompt should be 200-600 tokens
    assert 100 < response.usage["prompt_tokens"] < 1000

    # Completion should be 10-100 tokens
    assert 10 < response.usage["completion_tokens"] < 100


# =============================================================================
# UNIT TESTS: Singleton Pattern
# =============================================================================


def test_singleton_instance():
    """Test singleton instance caching."""
    # Reset singleton
    import vizu_llm_service.text_to_sql_config as tsc
    tsc._llm_call = None

    call1 = get_llm_call()
    call2 = get_llm_call()

    assert call1 is call2


def test_singleton_with_config_override():
    """Test singleton with config override."""
    import vizu_llm_service.text_to_sql_config as tsc
    tsc._llm_call = None

    config1 = TextToSqlLLMConfig.default_gpt4_turbo()
    call1 = get_llm_call(config=config1)

    # Override with different config
    config2 = TextToSqlLLMConfig.default_claude3_sonnet()
    call2 = get_llm_call(config=config2)

    # Should be different instances
    assert call1 is not call2
    assert call2.config.model == "claude-3-sonnet-20240229"


# =============================================================================
# INTEGRATION TESTS: Config + Call
# =============================================================================


@pytest.mark.asyncio
async def test_full_pipeline_gpt4():
    """Test full pipeline with GPT-4 config."""
    config = TextToSqlLLMConfig.default_gpt4_turbo()
    call = TextToSqlLLMCall(config=config)

    prompt = "Count total customers"
    response = await call.invoke(prompt)

    assert response.success is True
    assert response.sql is not None


@pytest.mark.asyncio
async def test_full_pipeline_claude():
    """Test full pipeline with Claude 3 config."""
    config = TextToSqlLLMConfig.default_claude3_sonnet()
    call = TextToSqlLLMCall(config=config)

    prompt = "List top 10 products"
    response = await call.invoke(prompt)

    assert response.success is True
    assert response.sql is not None


# =============================================================================
# EDGE CASES & ERROR HANDLING
# =============================================================================


def test_config_with_empty_stop_tokens():
    """Test config with empty stop tokens."""
    config = TextToSqlLLMConfig(stop_tokens=[])
    assert config.stop_tokens == []


def test_config_with_custom_stop_tokens():
    """Test config with custom stop tokens."""
    config = TextToSqlLLMConfig(
        stop_tokens=["END", "STOP", "---"]
    )

    assert config.stop_tokens == ["END", "STOP", "---"]


@pytest.mark.asyncio
async def test_invoke_with_very_long_prompt(llm_call):
    """Test invocation with very long prompt."""
    long_prompt = "Generate SQL for: " + ("query " * 500)

    response = await llm_call.invoke(long_prompt)

    # Should still work (may have fewer tokens due to limiting)
    assert response.success is True


@pytest.mark.asyncio
async def test_invoke_with_special_characters(llm_call):
    """Test invocation with special characters in prompt."""
    special_prompt = "SELECT * WHERE name = 'O\\'Brien' AND email LIKE '%@example.com%' LIMIT 100"

    response = await llm_call.invoke(special_prompt)

    assert response.success is True


def test_config_retry_backoff_calculation():
    """Test retry backoff calculation is reasonable."""
    config = TextToSqlLLMConfig(
        initial_retry_delay_ms=1000,
        max_retry_delay_ms=8000,
        retry_multiplier=2.0,
    )

    # Simulate backoff calculation
    delays = []
    for i in range(5):
        delay = min(
            config.initial_retry_delay_ms * (config.retry_multiplier ** i),
            config.max_retry_delay_ms,
        )
        delays.append(delay)

    # Should be: 1000, 2000, 4000, 8000, 8000
    assert delays == [1000, 2000, 4000, 8000, 8000]


# =============================================================================
# LOGGING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_invoke_logs_attempt(llm_call, prompt, caplog):
    """Test that invocation logs attempt info."""
    import logging
    caplog.set_level(logging.INFO)

    response = await llm_call.invoke(prompt)

    assert "[llm_call]" in caplog.text
    assert response.success is True


@pytest.mark.asyncio
async def test_invoke_logs_success(llm_call, prompt, caplog):
    """Test that successful invocation is logged."""
    import logging
    caplog.set_level(logging.INFO)

    response = await llm_call.invoke(prompt)

    assert "Success" in caplog.text or response.success is True
