"""
Built-in prompt templates for vizu_prompt_management
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PromptCategory(str, Enum):
    """Categories of prompts"""
    TEXT_TO_SQL = "text_to_sql"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    CUSTOM = "custom"


@dataclass
class PromptTemplateConfig:
    """Configuration for a prompt template"""
    name: str
    category: PromptCategory
    version: str = "1.0"
    description: str = ""
    template_text: str = ""
    required_variables: List[str] = field(default_factory=list)
    optional_variables: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


# Built-in templates

TEXT_TO_SQL_TEMPLATE = PromptTemplateConfig(
    name="text_to_sql_v1",
    category=PromptCategory.TEXT_TO_SQL,
    version="1.0",
    description="Text-to-SQL prompt template with role-based access control",
    template_text="""You are a SQL query generator for a multi-tenant business analytics platform. Your responsibility is to translate natural language questions into PostgreSQL queries that are safe, efficient, and respect data isolation constraints.

### Core Constraints

1. **Multi-Tenant Isolation**: NEVER query across client boundaries. Always include `client_id = '<TENANT_ID>'` filter.
2. **Role-Based Access**: Only query views and columns allowed for the user's role.
3. **Aggregate Whitelisting**: Only use COUNT, SUM, AVG, MIN, MAX - no other functions.
4. **LIMIT Enforcement**: Always include a LIMIT clause (max: <MAX_ROWS_LIMIT>).
5. **No DDL/DML**: Generate SELECT queries only. Never CREATE, ALTER, DROP, INSERT, UPDATE, DELETE.

### Available Schema

<SCHEMA_SNAPSHOT>

### Access Control Rules for role: <ROLE>

**Allowed Views**: <ALLOWED_VIEWS>
**Allowed Columns**: <ALLOWED_COLUMNS>
**Allowed Aggregates**: <ALLOWED_AGGREGATES>

### Constraints

- **Max Rows per Query**: <MAX_ROWS>
- **Max Execution Time**: <MAX_EXECUTION_TIME_SECONDS>s
- **Mandatory Filters**: <MANDATORY_FILTERS>

### Your Task

Translate this question to PostgreSQL: <QUESTION>

Return ONLY valid PostgreSQL SQL. No explanations, no markdown, no caveats.
""",
    required_variables=[
        "TENANT_ID",
        "ROLE",
        "SCHEMA_SNAPSHOT",
        "ALLOWED_VIEWS",
        "ALLOWED_COLUMNS",
        "ALLOWED_AGGREGATES",
        "MAX_ROWS",
        "MAX_EXECUTION_TIME_SECONDS",
        "MANDATORY_FILTERS",
        "QUESTION",
    ],
    optional_variables=[
        "DATE_RANGE_CONSTRAINTS",
        "ADDITIONAL_CONTEXT",
    ],
)

# Dictionary mapping template names to template configs
BUILTIN_TEMPLATES: Dict[str, PromptTemplateConfig] = {
    "text_to_sql_v1": TEXT_TO_SQL_TEMPLATE,
}

__all__ = [
    "PromptCategory",
    "PromptTemplateConfig",
    "TEXT_TO_SQL_TEMPLATE",
    "BUILTIN_TEMPLATES",
]
