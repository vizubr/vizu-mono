"""
Tests for TextToSqlPromptBuilder

Phase 1: Tests for prompt assembly with Phase 0 components (schema snapshot, allowlist)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from vizu_prompt_management.prompt_builder import (
    TextToSqlPromptBuilder,
    TextToSqlPromptContext,
    get_prompt_builder,
)
from vizu_sql_factory.schema_snapshot import (
    ColumnMetadata,
    ViewMetadata,
    SchemaSnapshot,
)
from vizu_sql_factory.allowlist import RoleConfig


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_schema_snapshot():
    """Create mock schema snapshot."""
    customers_cols = {
        "id": ColumnMetadata(
            name="id",
            type="integer",
            nullable=False,
            description="Customer ID",
            fk_target=None,
        ),
        "name": ColumnMetadata(
            name="name",
            type="text",
            nullable=False,
            description="Customer name",
            fk_target=None,
        ),
        "client_id": ColumnMetadata(
            name="client_id",
            type="uuid",
            nullable=False,
            description="Tenant identifier",
            fk_target=None,
        ),
    }

    customers_view = ViewMetadata(
        name="customers_view",
        columns=customers_cols,
        row_estimate=50000,
        description="Allowed customers view",
    )

    return SchemaSnapshot(
        views=[customers_view],
        join_paths=[],
        constraints=[],
    )


@pytest.fixture
def mock_role_config():
    """Create mock role config."""
    return RoleConfig(
        role="analyst",
        allowed_views={"customers_view", "data_sources_summary_view"},
        allowed_columns={
            "customers_view": {"id", "name", "client_id"},
            "data_sources_summary_view": {"*"},
        },
        allowed_aggregates={"COUNT", "SUM", "AVG"},
        max_rows=10000,
        max_execution_time_seconds=30,
    )


@pytest.fixture
def mock_template_path(tmp_path):
    """Create temporary template file."""
    template_content = """# Test Template

## Access Control Rules

### Role: <ROLE>

### Allowed Views

<ALLOWED_VIEWS>

### Constraints

- Max Rows: <MAX_ROWS>
- Max Time: <MAX_EXECUTION_TIME_SECONDS>s
- Aggregates: <ALLOWED_AGGREGATES>

### Mandatory Filters

<MANDATORY_FILTERS>

## Schema

<SCHEMA_SNAPSHOT>

---

## Your Task

Generate SQL now.
"""
    template_file = tmp_path / "text_to_sql.md"
    template_file.write_text(template_content)
    return template_file


@pytest.fixture
def prompt_builder(mock_template_path):
    """Create prompt builder with temporary template."""
    return TextToSqlPromptBuilder(template_path=mock_template_path)


# =============================================================================
# UNIT TESTS: Template Loading
# =============================================================================


def test_load_template_success(prompt_builder, mock_template_path):
    """Test loading template from file."""
    template = prompt_builder._load_template()

    assert template is not None
    assert "Access Control Rules" in template
    assert "<ROLE>" in template


def test_load_template_caching(prompt_builder):
    """Test template caching."""
    template1 = prompt_builder._load_template()
    template2 = prompt_builder._load_template()

    # Should return same object (cached)
    assert template1 is template2


def test_load_template_file_not_found():
    """Test error when template file not found."""
    builder = TextToSqlPromptBuilder(template_path=Path("/nonexistent/template.md"))

    with pytest.raises(FileNotFoundError):
        builder._load_template()


# =============================================================================
# UNIT TESTS: Schema Formatting
# =============================================================================


def test_format_schema_snapshot(prompt_builder, mock_schema_snapshot):
    """Test schema snapshot formatting."""
    formatted = prompt_builder._format_schema_snapshot(mock_schema_snapshot)

    assert "customers_view" in formatted
    assert "id" in formatted
    assert "name" in formatted


def test_format_allowed_views(prompt_builder, mock_role_config):
    """Test allowed views formatting."""
    formatted = prompt_builder._format_allowed_views(mock_role_config)

    assert "customers_view" in formatted
    assert "data_sources_summary_view" in formatted
    assert formatted.startswith("- ")


def test_format_allowed_views_empty():
    """Test allowed views formatting when empty."""
    role_config = RoleConfig(
        role="restricted",
        allowed_views=set(),
        allowed_columns={},
        allowed_aggregates={},
        max_rows=1000,
        max_execution_time_seconds=10,
    )
    builder = TextToSqlPromptBuilder()
    formatted = builder._format_allowed_views(role_config)

    assert "No views allowed" in formatted


def test_format_allowed_columns(prompt_builder, mock_role_config):
    """Test allowed columns formatting."""
    formatted = prompt_builder._format_allowed_columns(mock_role_config)

    assert "customers_view" in formatted
    assert "id" in formatted
    assert "all columns" in formatted  # data_sources_summary_view has "*"


def test_format_allowed_aggregates(prompt_builder, mock_role_config):
    """Test allowed aggregates formatting."""
    formatted = prompt_builder._format_allowed_aggregates(mock_role_config)

    assert "COUNT" in formatted
    assert "SUM" in formatted
    assert "AVG" in formatted
    assert "STDDEV" not in formatted


def test_format_mandatory_filters(prompt_builder):
    """Test mandatory filters formatting."""
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    formatted = prompt_builder._format_mandatory_filters(tenant_id)

    assert "client_id" in formatted
    assert tenant_id in formatted
    assert "multi-tenant" in formatted.lower()


# =============================================================================
# UNIT TESTS: Template Substitution
# =============================================================================


def test_substitute_template(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test template variable substitution."""
    template = prompt_builder._load_template()
    context = TextToSqlPromptContext(
        question="Test question",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    substituted = prompt_builder._substitute_template(template, context)

    # Check substitutions happened
    assert "<ROLE>" not in substituted
    assert "analyst" in substituted
    assert "<MAX_ROWS>" not in substituted
    assert "10000" in substituted
    assert "<ALLOWED_VIEWS>" not in substituted
    assert "customers_view" in substituted


def test_substitute_template_all_variables_replaced(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test that all template variables are replaced."""
    template = prompt_builder._load_template()
    context = TextToSqlPromptContext(
        question="Test question",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    substituted = prompt_builder._substitute_template(template, context)

    # Check no template variables remain
    for var_name, var_placeholder in prompt_builder.TEMPLATE_VARS.items():
        assert var_placeholder not in substituted, f"Variable {var_name} not substituted"


# =============================================================================
# UNIT TESTS: Context Validation
# =============================================================================


def test_context_valid(mock_schema_snapshot, mock_role_config):
    """Test context validation with all fields."""
    context = TextToSqlPromptContext(
        question="Test question",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    assert context.validate() is True


def test_context_invalid_missing_question(mock_schema_snapshot, mock_role_config):
    """Test context validation fails without question."""
    context = TextToSqlPromptContext(
        question="",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    assert context.validate() is False


def test_context_invalid_missing_schema(mock_role_config):
    """Test context validation fails without schema."""
    context = TextToSqlPromptContext(
        question="Test question",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=None,
        role_config=mock_role_config,
    )

    assert context.validate() is False


# =============================================================================
# INTEGRATION TESTS: Full Prompt Building
# =============================================================================


def test_build_complete_prompt(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test building a complete prompt."""
    context = TextToSqlPromptContext(
        question="How many customers do we have?",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    prompt = prompt_builder.build(context)

    # Check key components
    assert "How many customers do we have?" in prompt
    assert "analyst" in prompt
    assert "10000" in prompt
    assert "customers_view" in prompt
    assert "550e8400-e29b-41d4-a716-446655440000" in prompt
    assert "COUNT" in prompt
    assert "Generate SQL now:" in prompt


def test_build_with_optional_constraints(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test building prompt with optional constraints."""
    context = TextToSqlPromptContext(
        question="Sales in the last 30 days",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
        optional_constraints={"date_range": "last_30_days", "max_rows": 5000},
    )

    prompt = prompt_builder.build(context)

    assert "Sales in the last 30 days" in prompt
    assert "last_30_days" in prompt


def test_build_invalid_context_raises(prompt_builder, mock_role_config):
    """Test that build() raises on invalid context."""
    context = TextToSqlPromptContext(
        question="",  # Invalid: empty question
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=None,  # Invalid: no schema
        role_config=mock_role_config,
    )

    with pytest.raises(ValueError):
        prompt_builder.build(context)


# =============================================================================
# INTEGRATION TESTS: build_from_parts
# =============================================================================


def test_build_from_parts(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test convenience method build_from_parts."""
    prompt = prompt_builder.build_from_parts(
        question="Top 5 customers by revenue",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    assert "Top 5 customers by revenue" in prompt
    assert "analyst" in prompt


def test_build_from_parts_with_constraints(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test build_from_parts with optional constraints."""
    prompt = prompt_builder.build_from_parts(
        question="Q4 sales",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
        optional_constraints={"date_range": "year_to_date"},
    )

    assert "Q4 sales" in prompt
    assert "year_to_date" in prompt


# =============================================================================
# INTEGRATION TESTS: Singleton Instance
# =============================================================================


def test_get_prompt_builder_singleton():
    """Test singleton instance."""
    builder1 = get_prompt_builder()
    builder2 = get_prompt_builder()

    assert builder1 is builder2


def test_get_prompt_builder_with_custom_path(tmp_path):
    """Test singleton with custom template path."""
    template_file = tmp_path / "custom.md"
    template_file.write_text("Custom template")

    # Force reset of singleton
    import vizu_prompt_management.prompt_builder as pm
    pm._prompt_builder = None

    builder = get_prompt_builder(template_path=template_file)
    assert builder.template_path == template_file


# =============================================================================
# EDGE CASES & ERROR HANDLING
# =============================================================================


def test_format_aggregates_with_uncommon_functions(prompt_builder):
    """Test formatting of uncommon aggregate functions."""
    role_config = RoleConfig(
        role="advanced",
        allowed_views={"orders"},
        allowed_columns={"orders": {"*"}},
        allowed_aggregates={"COUNT", "SUM", "AVG", "STDDEV", "PERCENTILE_CONT"},
        max_rows=100000,
        max_execution_time_seconds=60,
    )

    formatted = prompt_builder._format_allowed_aggregates(role_config)

    assert "COUNT" in formatted
    assert "STDDEV" in formatted
    assert "PERCENTILE_CONT" in formatted


def test_build_with_very_long_question(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test building prompt with long question."""
    long_question = "Can you provide a detailed analysis of " * 20 + "customer behavior?"

    context = TextToSqlPromptContext(
        question=long_question,
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    prompt = prompt_builder.build(context)

    assert long_question in prompt
    assert "Generate SQL now:" in prompt


def test_build_with_special_characters_in_question(prompt_builder, mock_schema_snapshot, mock_role_config):
    """Test building prompt with special characters."""
    special_question = "Show me orders where amount > 1000 & status != 'cancelled'"

    context = TextToSqlPromptContext(
        question=special_question,
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    prompt = prompt_builder.build(context)

    assert special_question in prompt


# =============================================================================
# LOGGING TESTS
# =============================================================================


def test_build_logs_telemetry(prompt_builder, mock_schema_snapshot, mock_role_config, caplog):
    """Test that building logs telemetry information."""
    import logging
    caplog.set_level(logging.INFO)

    context = TextToSqlPromptContext(
        question="Test question",
        tenant_id="550e8400-e29b-41d4-a716-446655440000",
        role="analyst",
        schema_snapshot=mock_schema_snapshot,
        role_config=mock_role_config,
    )

    prompt_builder.build(context)

    assert "Building prompt" in caplog.text
    assert "Test question" in caplog.text
    assert "analyst" in caplog.text


def test_load_template_logs_success(prompt_builder, caplog):
    """Test that loading template logs success."""
    import logging
    caplog.set_level(logging.INFO)

    prompt_builder._load_template()

    assert "Loaded prompt template" in caplog.text


def test_template_not_found_logs_error():
    """Test that missing template logs error."""
    import logging

    builder = TextToSqlPromptBuilder(template_path=Path("/nonexistent/template.md"))

    with pytest.raises(FileNotFoundError):
        with pytest.raises(logging.DEBUG):  # Should log at error level
            builder._load_template()
