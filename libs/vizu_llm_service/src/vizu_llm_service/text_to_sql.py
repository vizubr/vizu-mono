"""
Text-to-SQL Integration - Phase 1 Refactored

Uses vizu_prompt_management for:
- Prompt loading and rendering
- Context variable extraction
- Database-backed overrides

This module simplifies by leveraging existing infrastructure.

Phase 1 Lesson Learned:
  Always search existing libs and connecting services for features before
  implementing. Avoid duplicate functionality across services.
"""

import logging
from typing import Optional
from uuid import UUID

from vizu_db_connector.database import get_db_session
from vizu_models import VizuClientContext
from vizu_prompt_management import PromptLoader, ContextVariableBuilder
from vizu_prompt_management.variables import VariableExtractor

logger = logging.getLogger(__name__)


class TextToSqlPrompt:
    """
    Simplified wrapper that leverages vizu_prompt_management.

    Instead of reimplementing context extraction and variable substitution,
    we use the centralized library that already handles:
    - Prompt loading (database + builtin fallback)
    - Variable extraction from client context
    - Template rendering with Jinja2
    - Client-specific overrides
    """

    def __init__(self, prompt_loader: Optional[PromptLoader] = None):
        """
        Initialize with optional prompt loader.

        Args:
            prompt_loader: PromptLoader instance (or uses default)
        """
        self.loader = prompt_loader or PromptLoader()

    async def build(
        self,
        question: str,
        tenant_id: str,
        role: str,
        schema_snapshot: Optional[dict] = None,
        role_config: Optional[dict] = None,
    ) -> str:
        """
        Build a complete text-to-sql prompt.

        Uses vizu_prompt_management to load and render the template.

        Args:
            question: User's natural language question
            tenant_id: Client ID for multi-tenant isolation
            role: User role (viewer, analyst, admin)
            schema_snapshot: Schema metadata (from SchemaSnapshotGenerator)
            role_config: Role-based constraints (from AllowlistConfig)

        Returns:
            Complete prompt ready for LLM

        Raises:
            PromptNotFoundError: If template not found
        """
        # Build variables using centralized builder
        builder = ContextVariableBuilder()
        builder.with_cliente_id(tenant_id)
        builder.with_custom("role", role)
        builder.with_custom("question", question)

        # Add schema and config if provided
        if schema_snapshot:
            builder.with_custom("schema_summary", self._format_schema(schema_snapshot))
        if role_config:
            builder.with_custom(
                "allowed_views", self._format_views(role_config.get("allowed_views", []))
            )
            builder.with_custom(
                "allowed_columns",
                self._format_columns(role_config.get("allowed_columns", [])),
            )
            builder.with_custom(
                "allowed_aggregates",
                ", ".join(role_config.get("allowed_aggregates", ["COUNT", "SUM", "AVG"])),
            )
            builder.with_custom(
                "max_rows_limit", role_config.get("max_rows", 1000)
            )
            builder.with_custom(
                "max_execution_time_seconds", role_config.get("max_execution_time_seconds", 30)
            )

        variables = builder.build_dict()

        # Load and render prompt using centralized loader
        loaded_prompt = await self.loader.load(
            "text-to-sql/v1",
            variables=variables,
            cliente_id=UUID(tenant_id) if tenant_id else None,
        )

        return loaded_prompt.content

    @staticmethod
    def _format_schema(schema_snapshot: dict) -> str:
        """Format schema snapshot for prompt."""
        if isinstance(schema_snapshot, str):
            return schema_snapshot

        tables = []
        for table_name, columns in schema_snapshot.items():
            col_list = ", ".join(columns) if isinstance(columns, list) else str(columns)
            tables.append(f"- **{table_name}**: {col_list}")

        return "\n".join(tables)

    @staticmethod
    def _format_views(views: list) -> str:
        """Format allowed views list."""
        if isinstance(views, str):
            return views
        return ", ".join(f"`{v}`" for v in views)

    @staticmethod
    def _format_columns(columns: list) -> str:
        """Format allowed columns list."""
        if isinstance(columns, str):
            return columns
        return ", ".join(f"`{c}`" for c in columns)

    async def build_from_context(
        self,
        question: str,
        context: VizuClientContext,
        schema_snapshot: Optional[dict] = None,
        role_config: Optional[dict] = None,
    ) -> str:
        """
        Build prompt from client context object.

        Extracts tenant_id and role from context using VariableExtractor.

        Args:
            question: User's question
            context: VizuClientContext
            schema_snapshot: Optional schema metadata
            role_config: Optional role constraints

        Returns:
            Complete prompt
        """
        # Extract variables from context using centralized extractor
        extracted_vars = VariableExtractor.from_client_context(context)

        # Build prompt
        return await self.build(
            question=question,
            tenant_id=str(context.id) if hasattr(context, "id") else "unknown",
            role=extracted_vars.tier or "viewer",
            schema_snapshot=schema_snapshot,
            role_config=role_config,
        )


# Singleton instance
_text_to_sql_prompt: Optional[TextToSqlPrompt] = None


def get_text_to_sql_prompt(
    prompt_loader: Optional[PromptLoader] = None,
) -> TextToSqlPrompt:
    """
    Get singleton instance of TextToSqlPrompt.

    Args:
        prompt_loader: Optional custom loader (for testing)

    Returns:
        TextToSqlPrompt instance
    """
    global _text_to_sql_prompt

    if _text_to_sql_prompt is None:
        _text_to_sql_prompt = TextToSqlPrompt(prompt_loader=prompt_loader)

    return _text_to_sql_prompt
