"""
Text-to-SQL Prompt Builder

Assembles complete prompts for LLM-based SQL generation, incorporating:
- Schema snapshots (allowed views/columns per role)
- Allowlist constraints (aggregates, limits, join paths)
- User context (tenant_id, role, optional constraints)
- Exemplars (learn-from examples)
- Safety instructions

Phase 1: Assembles prompts using Phase 0 components
Phase 2: Adds real schema introspection and RLS examples
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from vizu_sql_factory.schema_snapshot import SchemaSnapshot, SchemaSnapshotFormatter
from vizu_sql_factory.allowlist import AllowlistConfig, RoleConfig

logger = logging.getLogger(__name__)


@dataclass
class TextToSqlPromptContext:
    """Context for building a text-to-SQL prompt."""
    question: str  # User's natural language question
    tenant_id: str  # Tenant identifier
    role: str  # User role (viewer, analyst, admin)
    schema_snapshot: SchemaSnapshot  # Schema with role-based filtering
    role_config: RoleConfig  # Allowlist config for this role
    optional_constraints: Optional[Dict[str, Any]] = None  # e.g., date_range, max_rows

    def validate(self) -> bool:
        """Validate context has all required fields."""
        return all([
            self.question,
            self.tenant_id,
            self.role,
            self.schema_snapshot,
            self.role_config,
        ])


class TextToSqlPromptBuilder:
    """
    Builds complete prompts for text-to-SQL LLM generation.

    Orchestrates:
    1. Template loading (text_to_sql.md)
    2. Schema snapshot formatting
    3. Allowlist constraint formatting
    4. Exemplar selection
    5. Final prompt assembly
    """

    # Default template path (relative to this module)
    DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "templates" / "text_to_sql.md"

    # Substitution variables in template
    TEMPLATE_VARS = {
        "SCHEMA_SNAPSHOT": "<SCHEMA_SNAPSHOT>",
        "ROLE": "<ROLE>",
        "ALLOWED_VIEWS": "<ALLOWED_VIEWS>",
        "ALLOWED_COLUMNS": "<ALLOWED_COLUMNS>",
        "ALLOWED_AGGREGATES": "<ALLOWED_AGGREGATES>",
        "MAX_ROWS": "<MAX_ROWS>",
        "MAX_EXECUTION_TIME_SECONDS": "<MAX_EXECUTION_TIME_SECONDS>",
        "DATE_RANGE_CONSTRAINTS": "<DATE_RANGE_CONSTRAINTS>",
        "MANDATORY_FILTERS": "<MANDATORY_FILTERS>",
        "TENANT_ID": "<TENANT_ID>",
    }

    def __init__(self, template_path: Optional[Path] = None):
        """
        Initialize prompt builder.

        Args:
            template_path: Path to text_to_sql.md template. Defaults to bundled template.
        """
        self.template_path = template_path or self.DEFAULT_TEMPLATE_PATH
        self._template_cache: Optional[str] = None

    def _load_template(self) -> str:
        """Load prompt template from file."""
        if self._template_cache:
            return self._template_cache

        if not self.template_path.exists():
            logger.error(f"Template not found: {self.template_path}")
            raise FileNotFoundError(f"Prompt template not found: {self.template_path}")

        try:
            with open(self.template_path, "r") as f:
                self._template_cache = f.read()
            logger.info(f"Loaded prompt template from {self.template_path}")
            return self._template_cache
        except Exception as e:
            logger.exception(f"Error loading template: {e}")
            raise

    def _format_schema_snapshot(self, snapshot: SchemaSnapshot) -> str:
        """Format schema snapshot for prompt insertion."""
        formatter = SchemaSnapshotFormatter()
        return formatter.format_for_prompt(snapshot)

    def _format_allowed_views(self, role_config: RoleConfig) -> str:
        """Format allowed views for prompt."""
        views = role_config.allowed_views or []
        if not views:
            return "No views allowed (contact administrator)"

        lines = ["- " + view for view in sorted(views)]
        return "\n".join(lines)

    def _format_allowed_columns(self, role_config: RoleConfig) -> str:
        """Format allowed columns per view for prompt."""
        if not role_config.allowed_views:
            return "No columns allowed"

        lines = []
        for view in sorted(role_config.allowed_views):
            cols = role_config.allowed_columns.get(view, set())
            if cols == {"*"}:
                col_list = "all columns"
            else:
                col_list = ", ".join(sorted(cols)) if cols else "no columns"
            lines.append(f"- {view}: {col_list}")

        return "\n".join(lines)

    def _format_allowed_aggregates(self, role_config: RoleConfig) -> str:
        """Format allowed aggregates for prompt."""
        aggregates = role_config.allowed_aggregates or []
        if not aggregates:
            return "No aggregates allowed (SELECT only)"

        # Format with descriptions
        aggregate_descriptions = {
            "COUNT": "COUNT - Count rows",
            "SUM": "SUM - Sum numeric values",
            "AVG": "AVG - Average numeric values",
            "MIN": "MIN - Minimum value",
            "MAX": "MAX - Maximum value",
            "STDDEV": "STDDEV - Standard deviation (advanced)",
        }

        formatted = []
        for agg in sorted(aggregates):
            desc = aggregate_descriptions.get(agg, agg)
            formatted.append(f"- {desc}")

        return "\n".join(formatted)

    def _format_date_range_constraints(self,
                                      role_config: RoleConfig,
                                      optional_constraints: Optional[Dict[str, Any]]) -> str:
        """Format date range constraints."""
        constraints = []

        if optional_constraints and "date_range" in optional_constraints:
            dr = optional_constraints["date_range"]
            constraints.append(f"- Constrained to: {dr}")
        else:
            constraints.append("- User can specify: last_7_days, last_30_days, last_90_days, year_to_date")

        return "\n".join(constraints)

    def _format_mandatory_filters(self, tenant_id: str) -> str:
        """Format mandatory filters (always client_id)."""
        return f"- `client_id = '{tenant_id}'` (required for all queries - multi-tenant isolation)"

    def _substitute_template(self, template: str, context: TextToSqlPromptContext) -> str:
        """Substitute all template variables."""
        substitutions = {
            self.TEMPLATE_VARS["SCHEMA_SNAPSHOT"]: self._format_schema_snapshot(context.schema_snapshot),
            self.TEMPLATE_VARS["ROLE"]: context.role,
            self.TEMPLATE_VARS["ALLOWED_VIEWS"]: self._format_allowed_views(context.role_config),
            self.TEMPLATE_VARS["ALLOWED_COLUMNS"]: self._format_allowed_columns(context.role_config),
            self.TEMPLATE_VARS["ALLOWED_AGGREGATES"]: self._format_allowed_aggregates(context.role_config),
            self.TEMPLATE_VARS["MAX_ROWS"]: str(context.role_config.max_rows),
            self.TEMPLATE_VARS["MAX_EXECUTION_TIME_SECONDS"]: str(context.role_config.max_execution_time_seconds),
            self.TEMPLATE_VARS["DATE_RANGE_CONSTRAINTS"]: self._format_date_range_constraints(
                context.role_config,
                context.optional_constraints
            ),
            self.TEMPLATE_VARS["MANDATORY_FILTERS"]: self._format_mandatory_filters(context.tenant_id),
            self.TEMPLATE_VARS["TENANT_ID"]: context.tenant_id,
        }

        result = template
        for var, value in substitutions.items():
            result = result.replace(var, value)

        return result

    def build(self, context: TextToSqlPromptContext) -> str:
        """
        Build complete prompt for text-to-SQL generation.

        Args:
            context: TextToSqlPromptContext with question, tenant_id, role, schema, etc.

        Returns:
            Complete prompt ready for LLM consumption.

        Raises:
            ValueError: If context is invalid
            FileNotFoundError: If template not found
        """
        # Validate context
        if not context.validate():
            raise ValueError(f"Invalid context: missing required fields")

        logger.info(
            f"[prompt_builder] Building prompt: "
            f"question='{context.question[:50]}...', "
            f"tenant={context.tenant_id}, role={context.role}"
        )

        try:
            # Load template
            template = self._load_template()

            # Substitute variables
            prompt = self._substitute_template(template, context)

            # Append user question at the end
            prompt += f"\n\n## Your Task\n\n**Question**: {context.question}\n\nGenerate the SQL now:"

            logger.info(f"[prompt_builder] Prompt built successfully ({len(prompt)} chars)")
            return prompt

        except Exception as e:
            logger.exception(f"[prompt_builder] Error building prompt: {e}")
            raise

    def build_from_parts(
        self,
        question: str,
        tenant_id: str,
        role: str,
        schema_snapshot: SchemaSnapshot,
        role_config: RoleConfig,
        optional_constraints: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build prompt from individual parts.

        Convenience method that creates context and calls build().

        Args:
            question: User's natural language question
            tenant_id: Tenant identifier
            role: User role
            schema_snapshot: Schema with allowed views/columns
            role_config: Role-specific constraints
            optional_constraints: Optional filters

        Returns:
            Complete prompt
        """
        context = TextToSqlPromptContext(
            question=question,
            tenant_id=tenant_id,
            role=role,
            schema_snapshot=schema_snapshot,
            role_config=role_config,
            optional_constraints=optional_constraints,
        )
        return self.build(context)


# Singleton instance
_prompt_builder: Optional[TextToSqlPromptBuilder] = None


def get_prompt_builder(template_path: Optional[Path] = None) -> TextToSqlPromptBuilder:
    """
    Get prompt builder singleton instance.

    Args:
        template_path: Override template path (optional)

    Returns:
        TextToSqlPromptBuilder instance
    """
    global _prompt_builder

    if _prompt_builder is None:
        _prompt_builder = TextToSqlPromptBuilder(template_path=template_path)

    return _prompt_builder
