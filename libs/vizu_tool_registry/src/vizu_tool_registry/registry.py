"""
vizu_tool_registry.registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Central registry of all available tools.

This module provides the ToolRegistry class which maintains a catalog of
all builtin and Docker MCP tools, with methods for querying and validating
tool access based on client configuration.
"""

import logging
from typing import Dict, List, Optional, Tuple

from .tool_metadata import ToolMetadata, ToolCategory, TierLevel

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry of all available tools.

    Provides methods for:
    - Querying available tools based on client configuration
    - Validating tool access permissions
    - Discovering Docker MCP tools (when enabled)

    Usage:
        # Get tools for a client
        tools = ToolRegistry.get_available_tools(
            enabled_tools=["executar_rag_cliente"],
            tier="BASIC"
        )

        # Validate configuration
        is_valid, errors = ToolRegistry.validate_client_tools(
            enabled_tools=["executar_sql_agent"],
            tier="BASIC"
        )
    """

    # =========================================================================
    # BUILTIN TOOLS - Always available in FastMCP
    # =========================================================================
    BUILTIN_TOOLS: Dict[str, ToolMetadata] = {
        "executar_rag_cliente": ToolMetadata(
            name="executar_rag_cliente",
            category=ToolCategory.RAG,
            description="Busca informações na base de conhecimento do cliente (RAG)",
            tier_required=TierLevel.BASIC,
            requires_confirmation=False,
            tags=["rag", "search", "knowledge-base"],
        ),
        "executar_sql_agent": ToolMetadata(
            name="executar_sql_agent",
            category=ToolCategory.SQL,
            description=(
                "Executes SQL queries on structured data (products, orders, inventory). "
                "Only requires 'query' parameter - client_id is auto-injected."
            ),
            tier_required=TierLevel.SME,
            requires_confirmation=False,
            tags=["sql", "database", "analytics"],
        ),
        "agendar_consulta": ToolMetadata(
            name="agendar_consulta",
            category=ToolCategory.SCHEDULING,
            description="Agenda consultas ou compromissos no calendário",
            tier_required=TierLevel.SME,
            requires_confirmation=True,
            tags=["scheduling", "calendar", "appointments"],
        ),
        "ferramenta_publica_de_teste": ToolMetadata(
            name="ferramenta_publica_de_teste",
            category=ToolCategory.PUBLIC,
            description="Ferramenta de diagnóstico interno (sempre disponível)",
            tier_required=TierLevel.FREE,
            requires_confirmation=False,
            tags=["test", "diagnostic", "public"],
        ),
    }

    # =========================================================================
    # GOOGLE INTEGRATION TOOLS
    # =========================================================================
    GOOGLE_TOOLS: Dict[str, ToolMetadata] = {
        "google_calendar_list_events": ToolMetadata(
            name="google_calendar_list_events",
            category=ToolCategory.GOOGLE,
            description="Lista eventos do Google Calendar",
            tier_required=TierLevel.SME,
            requires_confirmation=False,
            tags=["google", "calendar", "events"],
        ),
        "google_calendar_create_event": ToolMetadata(
            name="google_calendar_create_event",
            category=ToolCategory.GOOGLE,
            description="Cria eventos no Google Calendar",
            tier_required=TierLevel.SME,
            requires_confirmation=True,
            tags=["google", "calendar", "create"],
        ),
        "google_drive_list_files": ToolMetadata(
            name="google_drive_list_files",
            category=ToolCategory.GOOGLE,
            description="Lista arquivos do Google Drive",
            tier_required=TierLevel.SME,
            requires_confirmation=False,
            tags=["google", "drive", "files"],
        ),
    }

    # =========================================================================
    # DOCKER MCP TOOLS - Optional, loaded from Docker MCP toolkit
    # =========================================================================
    DOCKER_MCP_TOOLS: Dict[str, ToolMetadata] = {
        "github_read": ToolMetadata(
            name="github_read",
            category=ToolCategory.DOCKER_MCP,
            description="Read GitHub repositories, issues, and pull requests",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="github",
            requires_confirmation=False,
            tags=["github", "vcs", "code"],
        ),
        "github_write": ToolMetadata(
            name="github_write",
            category=ToolCategory.DOCKER_MCP,
            description="Create/update GitHub issues and pull requests",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="github",
            requires_confirmation=True,
            tags=["github", "vcs", "code"],
        ),
        "slack_read": ToolMetadata(
            name="slack_read",
            category=ToolCategory.DOCKER_MCP,
            description="Read Slack messages and channels",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="slack",
            requires_confirmation=False,
            tags=["slack", "messaging", "chat"],
        ),
        "slack_send": ToolMetadata(
            name="slack_send",
            category=ToolCategory.DOCKER_MCP,
            description="Send Slack messages",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="slack",
            requires_confirmation=True,
            tags=["slack", "messaging", "chat"],
        ),
        "stripe_read": ToolMetadata(
            name="stripe_read",
            category=ToolCategory.DOCKER_MCP,
            description="Read Stripe payment information",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="stripe",
            requires_confirmation=False,
            tags=["stripe", "payments", "billing"],
        ),
        "stripe_charge": ToolMetadata(
            name="stripe_charge",
            category=ToolCategory.DOCKER_MCP,
            description="Process Stripe payments",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="stripe",
            requires_confirmation=True,
            tags=["stripe", "payments", "billing"],
        ),
        "postgres_query": ToolMetadata(
            name="postgres_query",
            category=ToolCategory.DOCKER_MCP,
            description="Query external PostgreSQL databases",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="postgres",
            requires_confirmation=False,
            tags=["postgres", "database", "sql"],
        ),
        "jira_read": ToolMetadata(
            name="jira_read",
            category=ToolCategory.DOCKER_MCP,
            description="Read Jira issues and projects",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="jira",
            requires_confirmation=False,
            tags=["jira", "project-management", "issues"],
        ),
        "jira_write": ToolMetadata(
            name="jira_write",
            category=ToolCategory.DOCKER_MCP,
            description="Create/update Jira issues",
            tier_required=TierLevel.ENTERPRISE,
            docker_mcp_integration="jira",
            requires_confirmation=True,
            tags=["jira", "project-management", "issues"],
        ),
    }

    # =========================================================================
    # CLASS METHODS
    # =========================================================================

    @classmethod
    def get_all_tools(cls) -> Dict[str, ToolMetadata]:
        """Get all registered tools (builtin + Google + Docker MCP)."""
        all_tools = {}
        all_tools.update(cls.BUILTIN_TOOLS)
        all_tools.update(cls.GOOGLE_TOOLS)
        all_tools.update(cls.DOCKER_MCP_TOOLS)
        return all_tools

    @classmethod
    def get_tool(cls, tool_name: str) -> Optional[ToolMetadata]:
        """
        Get tool metadata by name.

        Args:
            tool_name: Name of the tool to look up

        Returns:
            ToolMetadata if found, None otherwise
        """
        return (
            cls.BUILTIN_TOOLS.get(tool_name)
            or cls.GOOGLE_TOOLS.get(tool_name)
            or cls.DOCKER_MCP_TOOLS.get(tool_name)
        )

    @classmethod
    def get_available_tools(
        cls,
        enabled_tools: List[str],
        tier: str,
        include_docker_mcp: bool = False,
        include_google: bool = True,
    ) -> List[ToolMetadata]:
        """
        Get tools available for a client based on enabled list and tier.

        This is the main method used by agents to determine which tools
        are available for a specific client.

        Args:
            enabled_tools: List of tool names from client config
            tier: Client tier (BASIC, SME, ENTERPRISE)
            include_docker_mcp: Whether to check Docker MCP tools
            include_google: Whether to check Google integration tools

        Returns:
            List of accessible ToolMetadata objects
        """
        available = []

        # Always check builtin tools
        for tool_name in enabled_tools:
            tool = cls.BUILTIN_TOOLS.get(tool_name)
            if tool and tool.enabled and tool.is_accessible_by_tier(tier):
                available.append(tool)

        # Optionally check Google tools
        if include_google:
            for tool_name in enabled_tools:
                tool = cls.GOOGLE_TOOLS.get(tool_name)
                if tool and tool.enabled and tool.is_accessible_by_tier(tier):
                    available.append(tool)

        # Optionally check Docker MCP tools (only for ENTERPRISE tier)
        if include_docker_mcp:
            for tool_name in enabled_tools:
                tool = cls.DOCKER_MCP_TOOLS.get(tool_name)
                if tool and tool.enabled and tool.is_accessible_by_tier(tier):
                    available.append(tool)

        logger.debug(
            f"Available tools for tier {tier}: {[t.name for t in available]}"
        )
        return available

    @classmethod
    def validate_client_tools(
        cls, enabled_tools: List[str], tier: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate that client's enabled_tools are compatible with tier.

        Use this to check configuration validity, e.g., when updating
        a client's tier or enabled tools.

        Args:
            enabled_tools: List of tool names from client config
            tier: Client tier as string

        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors = []

        for tool_name in enabled_tools:
            tool = cls.get_tool(tool_name)

            if not tool:
                errors.append(f"{tool_name} (tool not found in registry)")
            elif not tool.is_accessible_by_tier(tier):
                errors.append(
                    f"{tool_name} (requires {tool.tier_required.value}, "
                    f"client has {tier})"
                )
            elif not tool.enabled:
                errors.append(f"{tool_name} (tool is globally disabled)")

        is_valid = len(errors) == 0
        return is_valid, errors

    @classmethod
    def get_tools_for_tier(cls, tier: str) -> List[ToolMetadata]:
        """
        Get all tools accessible at a given tier.

        Useful for showing what tools become available at each tier.

        Args:
            tier: Target tier

        Returns:
            List of tools accessible at that tier
        """
        accessible = []

        for tool in cls.get_all_tools().values():
            if tool.enabled and tool.is_accessible_by_tier(tier):
                accessible.append(tool)

        return accessible

    @classmethod
    def get_tools_by_category(cls, category: ToolCategory) -> List[ToolMetadata]:
        """
        Get all tools in a specific category.

        Args:
            category: Tool category to filter by

        Returns:
            List of tools in that category
        """
        return [
            tool
            for tool in cls.get_all_tools().values()
            if tool.category == category
        ]

    @classmethod
    def get_confirmation_required_tools(cls) -> List[ToolMetadata]:
        """Get all tools that require user confirmation."""
        return [
            tool
            for tool in cls.get_all_tools().values()
            if tool.requires_confirmation
        ]

    @classmethod
    def register_custom_tool(cls, tool: ToolMetadata) -> None:
        """
        Register a custom tool at runtime.

        Use this for dynamic tool registration, e.g., from database
        or configuration files.

        Args:
            tool: ToolMetadata to register
        """
        cls.BUILTIN_TOOLS[tool.name] = tool
        logger.info(f"Registered custom tool: {tool.name}")

    @classmethod
    def get_tool_names_for_legacy_flags(
        cls,
        rag_enabled: bool,
        sql_enabled: bool,
        scheduling_enabled: bool,
    ) -> List[str]:
        """
        Convert legacy boolean flags to enabled_tools list.

        Helper for backward compatibility during migration.

        Args:
            rag_enabled: Legacy ferramenta_rag_habilitada flag
            sql_enabled: Legacy ferramenta_sql_habilitada flag
            scheduling_enabled: Legacy ferramenta_agendamento_habilitada flag

        Returns:
            List of tool names
        """
        tools = []
        if rag_enabled:
            tools.append("executar_rag_cliente")
        if sql_enabled:
            tools.append("executar_sql_agent")
        if scheduling_enabled:
            tools.append("agendar_consulta")
        return tools

    @classmethod
    def register_docker_mcp_tools(cls, docker_tools: Dict[str, ToolMetadata]) -> int:
        """
        Register Docker MCP tools discovered at runtime.

        This is called by DockerMCPAdapter after discovering running
        Docker MCP containers.

        Args:
            docker_tools: Dict mapping tool_name -> ToolMetadata

        Returns:
            Number of tools registered
        """
        count = 0
        for tool_name, tool_metadata in docker_tools.items():
            if tool_name not in cls.DOCKER_MCP_TOOLS:
                cls.DOCKER_MCP_TOOLS[tool_name] = tool_metadata
                logger.info(f"Registered Docker MCP tool: {tool_name}")
                count += 1
            else:
                # Update existing tool metadata
                cls.DOCKER_MCP_TOOLS[tool_name] = tool_metadata
                logger.debug(f"Updated Docker MCP tool: {tool_name}")
        return count

    @classmethod
    def get_docker_mcp_integrations(cls) -> Dict[str, List[str]]:
        """
        Get all Docker MCP integrations and their tools.

        Returns:
            Dict mapping integration_name -> list of tool names
        """
        integrations: Dict[str, List[str]] = {}
        for tool in cls.DOCKER_MCP_TOOLS.values():
            if tool.docker_mcp_integration:
                if tool.docker_mcp_integration not in integrations:
                    integrations[tool.docker_mcp_integration] = []
                integrations[tool.docker_mcp_integration].append(tool.name)
        return integrations

    @classmethod
    def is_docker_mcp_tool(cls, tool_name: str) -> bool:
        """Check if a tool is a Docker MCP tool."""
        return tool_name in cls.DOCKER_MCP_TOOLS
