"""
vizu_prompt_management - Centralized prompt management for Vizu services.

This library provides:
- Prompt loading from database and files
- Versioning and A/B testing
- Variable substitution with Jinja2
- Client-specific overrides
- MCP integration
"""

__version__ = "0.1.0"

from vizu_prompt_management.loader import PromptLoader, LoadedPrompt
from vizu_prompt_management.manager import PromptManager, PromptVersion
from vizu_prompt_management.variables import VariableExtractor, PromptVariables, ContextVariableBuilder
from vizu_prompt_management.renderer import TemplateRenderer

# Phase 1: Text-to-SQL prompt building
from vizu_prompt_management.prompt_builder import (
    TextToSqlPromptBuilder,
    TextToSqlPromptContext,
    get_prompt_builder,
)

# Templates are exposed as module
from vizu_prompt_management import templates

__all__ = [
    "__version__",
    # Loader
    "PromptLoader",
    "LoadedPrompt",
    # Manager
    "PromptManager",
    "PromptVersion",
    # Variables
    "VariableExtractor",
    "PromptVariables",
    "ContextVariableBuilder",
    # Renderer
    "TemplateRenderer",
    # Templates module
    "templates",
    # Phase 1: Text-to-SQL
    "TextToSqlPromptBuilder",
    "TextToSqlPromptContext",
    "get_prompt_builder",
]
