"""
Text-to-SQL LLM Configuration and Call Wrapper

Phase 1.3: Configure LLM parameters for safe SQL generation
- Model selection (gpt-4-turbo, claude-3-sonnet)
- Deterministic output (temperature=0.0)
- Safety parameters (max_tokens, stop_tokens)
- Retry policy (exponential backoff)
- Timeout management

**Integration Note (Phase 1 Refactoring)**:
For prompt building, use text_to_sql.py (TextToSqlPrompt wrapper).
It provides:
- Context extraction from VizuClientContext
- Variable substitution with schema info, allowed views/columns
- Template loading with database fallback (via vizu_prompt_management)

This config file focuses ONLY on LLM call parameters and response handling.
The prompt assembly is handled by TextToSqlPrompt in text_to_sql.py.

Example workflow:
  1. Build prompt: prompt = await TextToSqlPrompt.build_from_context(question, context)
  2. Configure LLM: config = TextToSqlLLMConfig.default_gpt4_turbo()
  3. Call LLM: llm_call = TextToSqlLLMCall(config)
  4. Invoke: response = await llm_call.invoke(prompt)
"""

import logging
import asyncio
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
import time

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMModel(Enum):
    """Supported LLM models."""
    GPT4_TURBO = "gpt-4-turbo"
    GPT4_TURBO_VISION = "gpt-4-turbo-preview"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"


@dataclass
class TextToSqlLLMConfig:
    """
    Configuration for Text-to-SQL LLM calls.

    This class encapsulates all parameters needed for safe, deterministic
    SQL generation via LLM.

    **Key Design Decisions**:
    - temperature=0.0: Deterministic output (no randomness in SQL)
    - max_tokens=500: Limit response size (SQL is typically <200 tokens)
    - stop_tokens: ["UNABLE", ";", "\n\n"] (stop on error, end of SQL, double newline)
    - max_retries=3: Exponential backoff on transient errors
    - timeout_seconds=30: Prevent hanging on slow models
    """

    # Model selection
    model: str = "gpt-4-turbo"  # Default to GPT-4 Turbo
    provider: str = "openai"  # Provider (openai or anthropic)

    # Temperature and randomness
    temperature: float = 0.0  # Deterministic (no randomness)
    top_p: float = 1.0  # Nucleus sampling (disabled, use temperature)

    # Token management
    max_tokens: int = 500  # Max response length (SQL typically <200 tokens)
    max_input_tokens: Optional[int] = None  # Max input length (provider-dependent)

    # Safety and stopping
    stop_tokens: List[str] = None  # Stop on these strings
    safety_instructions_enabled: bool = True  # Include safety guardrails in system prompt

    # Retry policy
    max_retries: int = 3  # Max retry attempts
    initial_retry_delay_ms: int = 1000  # Start with 1 second
    max_retry_delay_ms: int = 8000  # Cap at 8 seconds (1s, 2s, 4s, 8s)
    retry_multiplier: float = 2.0  # Exponential backoff factor

    # Timeout and latency
    timeout_seconds: float = 30.0  # Max wait time per call
    request_timeout_seconds: float = 35.0  # HTTP timeout (slightly higher)

    # Logging and observability
    log_prompts: bool = False  # Log full prompt to console (security: disable in prod)
    log_responses: bool = False  # Log full response (security: disable in prod)
    include_usage_stats: bool = True  # Track token usage

    # API credentials and endpoints
    api_key: Optional[str] = None  # Will be loaded from environment
    api_base: Optional[str] = None  # Custom API endpoint

    def __post_init__(self):
        """Validate configuration and set defaults."""
        if self.stop_tokens is None:
            self.stop_tokens = ["UNABLE", ";", "\n\n"]

        # Validate temperature
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"Temperature must be 0.0-2.0, got {self.temperature}")

        # Validate tokens
        if self.max_tokens < 100 or self.max_tokens > 4000:
            logger.warning(f"max_tokens={self.max_tokens} unusual (recommend 100-2000)")

        # Validate retry settings
        if self.max_retries < 0 or self.max_retries > 10:
            raise ValueError(f"max_retries must be 0-10, got {self.max_retries}")

        if self.initial_retry_delay_ms < 100:
            logger.warning(f"initial_retry_delay_ms={self.initial_retry_delay_ms} < 100ms")

        # Validate timeout
        if self.timeout_seconds < 5:
            logger.warning(f"timeout_seconds={self.timeout_seconds} < 5s (may timeout quickly)")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def default_gpt4_turbo(cls) -> "TextToSqlLLMConfig":
        """Create default config for GPT-4 Turbo."""
        return cls(
            model="gpt-4-turbo",
            provider="openai",
            temperature=0.0,
            max_tokens=500,
        )

    @classmethod
    def default_claude3_sonnet(cls) -> "TextToSqlLLMConfig":
        """Create default config for Claude 3 Sonnet."""
        return cls(
            model="claude-3-sonnet-20240229",
            provider="anthropic",
            temperature=0.0,
            max_tokens=500,
        )


@dataclass
class TextToSqlLLMResponse:
    """Response from LLM call."""
    success: bool  # Whether call succeeded
    sql: Optional[str] = None  # Generated SQL (null if failed)
    raw_response: Optional[str] = None  # Full LLM response before parsing
    error: Optional[str] = None  # Error message if failed
    error_code: Optional[str] = None  # Error code for categorization
    usage: Optional[Dict[str, int]] = None  # Token usage {prompt_tokens, completion_tokens, total_tokens}
    latency_ms: float = 0.0  # Total time taken
    retry_count: int = 0  # Number of retries used
    stop_reason: Optional[str] = None  # Why LLM stopped (stop_sequence, max_tokens, etc.)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class TextToSqlLLMCall:
    """
    Wrapper for Text-to-SQL LLM calls.

    Responsibilities:
    1. Load LLM credentials from environment
    2. Format system prompt with safety instructions
    3. Build user message with question
    4. Call LLM with configured parameters
    5. Parse response to extract SQL
    6. Retry on transient errors (exponential backoff)
    7. Track metrics (latency, token usage)

    Phase 1.3: Stub implementation with mock calls
    Phase 2: Real implementation with OpenAI/Anthropic SDKs
    """

    def __init__(self, config: Optional[TextToSqlLLMConfig] = None):
        """
        Initialize LLM call wrapper.

        Args:
            config: LLM configuration. Defaults to GPT-4 Turbo.
        """
        self.config = config or TextToSqlLLMConfig.default_gpt4_turbo()
        self._load_api_key()
        logger.info(f"[llm_call] Initialized with model: {self.config.model}")

    def _load_api_key(self) -> None:
        """Load API key from environment if not provided."""
        import os

        if self.config.api_key:
            return  # Already provided

        # Try to load from environment
        if self.config.provider == "openai":
            self.config.api_key = os.getenv("OPENAI_API_KEY")
            if not self.config.api_key:
                logger.warning("OPENAI_API_KEY not found in environment")
        elif self.config.provider == "anthropic":
            self.config.api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.config.api_key:
                logger.warning("ANTHROPIC_API_KEY not found in environment")

    def _build_system_prompt(self) -> str:
        """Build system prompt with safety instructions."""
        if not self.config.safety_instructions_enabled:
            return "You are a helpful SQL assistant."

        return (
            "You are a SQL query generator for a multi-tenant analytics platform. "
            "Your task is to generate safe, valid PostgreSQL SELECT queries. "
            "CRITICAL CONSTRAINTS:\n"
            "1. NEVER bypass tenant isolation - always include client_id filter\n"
            "2. NO DDL/DML - SELECT only\n"
            "3. LIMIT results - max 100,000 rows\n"
            "4. Aggregates only: COUNT, SUM, AVG, MIN, MAX\n"
            "5. If cannot generate safe SQL, respond with: UNABLE\n"
            "6. Return ONLY the SQL query, no explanation"
        )

    async def invoke(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> TextToSqlLLMResponse:
        """
        Invoke LLM with exponential backoff retry.

        Args:
            prompt: User message (assembled by PromptBuilder)
            system_prompt: Override system prompt (optional)

        Returns:
            TextToSqlLLMResponse with SQL or error
        """
        system_prompt = system_prompt or self._build_system_prompt()

        start_time = time.time()
        retry_count = 0

        while retry_count <= self.config.max_retries:
            try:
                logger.info(
                    f"[llm_call] Invoke attempt {retry_count + 1}/{self.config.max_retries + 1}, "
                    f"model={self.config.model}"
                )

                # Phase 1.3: Stub implementation (returns mock SQL)
                # Phase 2: Real implementation with OpenAI/Anthropic SDK
                response = await self._call_llm_stub(prompt, system_prompt)

                latency_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"[llm_call] Success: latency={latency_ms:.1f}ms, "
                    f"retry_count={retry_count}, "
                    f"tokens={response.usage.get('total_tokens', 'unknown') if response.usage else 'unknown'}"
                )

                return response

            except Exception as e:
                retry_count += 1

                if retry_count > self.config.max_retries:
                    latency_ms = (time.time() - start_time) * 1000
                    logger.exception(
                        f"[llm_call] Failed after {retry_count} attempts: {e}, "
                        f"latency={latency_ms:.1f}ms"
                    )
                    return TextToSqlLLMResponse(
                        success=False,
                        error=str(e),
                        error_code="MAX_RETRIES_EXCEEDED",
                        latency_ms=latency_ms,
                        retry_count=retry_count - 1,
                    )

                # Calculate exponential backoff
                delay_ms = min(
                    self.config.initial_retry_delay_ms * (self.config.retry_multiplier ** retry_count),
                    self.config.max_retry_delay_ms,
                )
                delay_sec = delay_ms / 1000.0

                logger.warning(
                    f"[llm_call] Attempt {retry_count} failed: {e}, "
                    f"retrying in {delay_sec:.1f}s"
                )

                await asyncio.sleep(delay_sec)

    async def _call_llm_stub(
        self,
        prompt: str,
        system_prompt: str,
    ) -> TextToSqlLLMResponse:
        """
        Stub LLM call for Phase 1.3 testing.

        Phase 2 will replace with real OpenAI/Anthropic SDK calls.

        Args:
            prompt: User message
            system_prompt: System instructions

        Returns:
            Mock response with realistic SQL
        """
        # Simulate LLM latency
        await asyncio.sleep(0.1)

        if self.config.log_prompts:
            logger.debug(f"[llm_call] System: {system_prompt[:200]}...")
            logger.debug(f"[llm_call] User: {prompt[:200]}...")

        # Check for "UNABLE" in prompt (test error case)
        if "impossible" in prompt.lower() or "no solution" in prompt.lower():
            return TextToSqlLLMResponse(
                success=False,
                raw_response="UNABLE",
                sql=None,
                error="LLM returned UNABLE - cannot generate safe SQL",
                error_code="UNABLE_RESPONSE",
                usage={"prompt_tokens": 150, "completion_tokens": 2, "total_tokens": 152},
                latency_ms=100.0,
                stop_reason="stop_sequence",
            )

        # Default mock SQL response (from Phase 0.6 exemplar)
        mock_sql = (
            "SELECT COUNT(*) AS total_records "
            "FROM customers_view "
            "WHERE client_id = '{tenant_id}' "
            "LIMIT 100"
        )

        return TextToSqlLLMResponse(
            success=True,
            sql=mock_sql,
            raw_response=mock_sql,
            error=None,
            usage={
                "prompt_tokens": 450,  # Typical prompt size with template
                "completion_tokens": 30,  # SQL is usually 20-50 tokens
                "total_tokens": 480,
            },
            latency_ms=150.0,  # Typical LLM latency
            retry_count=0,
            stop_reason="stop_sequence",  # Stopped on LIMIT 100
        )

    async def invoke_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> TextToSqlLLMResponse:
        """
        Synchronous wrapper for invoke().

        For backwards compatibility with sync code.

        Args:
            prompt: User message
            system_prompt: Override system prompt (optional)

        Returns:
            TextToSqlLLMResponse
        """
        return await self.invoke(prompt, system_prompt)


# Singleton instance (created on demand)
_llm_call: Optional[TextToSqlLLMCall] = None


def get_llm_call(config: Optional[TextToSqlLLMConfig] = None) -> TextToSqlLLMCall:
    """
    Get LLM call singleton instance.

    Args:
        config: Override config (optional)

    Returns:
        TextToSqlLLMCall instance
    """
    global _llm_call

    if _llm_call is None:
        _llm_call = TextToSqlLLMCall(config=config)
    elif config is not None:
        # Reset if config provided
        _llm_call = TextToSqlLLMCall(config=config)

    return _llm_call
