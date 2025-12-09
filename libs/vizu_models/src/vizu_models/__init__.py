# vizu_models/__init__.py (Versão Corrigida para Exportação)

from .cliente_vizu import (
    ClienteVizu,
    ClienteVizuCreate,
    ClienteVizuRead,
    ClienteVizuReadWithRelations,
    ClienteVizuUpdate,
)
from .configuracao_negocio import (
    ConfiguracaoNegocio,
    ConfiguracaoNegocioBase,
    ConfiguracaoNegocioCreate,
    ConfiguracaoNegocioRead,
    ConfiguracaoNegocioUpdate,
)
from .credencial_servico_externo import (
    CredencialServicoExterno,
    CredencialServicoExternoBase,
    CredencialServicoExternoCreate,
    CredencialServicoExternoInDB,
)
from .fonte_de_dados import FonteDeDados
from .cliente_final import (
    ClienteFinal,
    ClienteFinalCreate,
    ClienteFinalRead,
    ClienteFinalUpdate,
)
from .conversa import (
    Conversa,
    ConversaBase,
    ConversaCreate,
    ConversaInDB,
    Mensagem,
    MensagemBase,
    MensagemCreate,
    MensagemInDB,
    Remetente,
)
from .vizu_client_context import VizuClientContext
from .safe_client_context import SafeClientContext, InternalClientContext
from .seed_clients import SEED_CLIENTS, get_client_by_name, get_all_rag_collections
from sqlmodel import SQLModel
from .enums import TipoCliente, TierCliente, TipoFonte, ToolCategory

# MCP Resources & Prompts support
from .prompt_template import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateRead,
    PromptTemplateUpdate,
)
from .knowledge_base_config import (
    KnowledgeBaseConfig,
    KnowledgeBaseConfigCreate,
    KnowledgeBaseConfigRead,
    KnowledgeBaseConfigUpdate,
)
from .sql_schema_config import (
    SqlTableConfig,
    SqlTableConfigCreate,
    SqlTableConfigRead,
    SqlTableConfigUpdate,
)

# Agent Types (shared across all agents/LangGraph flows)
from .agent_types import (
    # Elicitation
    ElicitationType,
    ElicitationOption,
    ElicitationRequest,
    ElicitationResponse,
    # Tool Management
    ToolInfo,
    ToolExecutionResult,
    # Model/LLM
    ModelInfo,
    # Chat/Message
    AgentChatRequest,
    AgentChatResponse,
    # Client Context
    ClientContextResponse,
)

# HITL (Human-in-the-Loop) support
from .hitl import (
    HitlCriteriaType,
    HitlReviewStatus,
    HitlFeedbackType,
    HitlCriterion,
    HitlConfig,
    HitlReview,
    HitlReviewCreate,
    HitlReviewRead,
    HitlReviewUpdate,
    HitlQueueStats,
    HitlDecision,
)

# Experiment Suite (Dataset Generation)
from .experiment import (
    ExperimentStatus,
    CaseOutcome,
    ClassificationResult,
    TestCaseDefinition,
    ClientVariant,
    HitlRoutingConfig,
    LangfuseConfig,
    ExperimentManifest,
    ExperimentRunSummary,
    ExperimentProgress,
    ExperimentRun,
    ExperimentCase,
)

# Integration models
from .integration import (
    IntegrationConfig,
    IntegrationTokens,
    OAuthTokenResponse,
    IntegrationProvider,
)


class Base(SQLModel):
    """
    Classe base que herda de SQLModel. Usada pelo Alembic como target_metadata.
    """

    pass


__all__ = [
    "Base",
    "ClienteVizu",
    "ClienteVizuCreate",
    "ClienteVizuRead",
    "ClienteVizuReadWithRelations",
    "ClienteVizuUpdate",  # Deve ser a classe única ClienteVizuUpdate
    "ConfiguracaoNegocio",
    "ConfiguracaoNegocioBase",
    "ConfiguracaoNegocioCreate",
    "ConfiguracaoNegocioRead",
    "ConfiguracaoNegocioUpdate",
    "CredencialServicoExterno",
    "CredencialServicoExternoBase",
    "CredencialServicoExternoCreate",
    "CredencialServicoExternoInDB",
    "FonteDeDados",
    "ClienteFinal",
    "ClienteFinalCreate",
    "ClienteFinalRead",
    "ClienteFinalUpdate",
    "Conversa",
    "ConversaBase",
    "ConversaCreate",
    "ConversaInDB",
    "Mensagem",
    "MensagemBase",
    "MensagemCreate",
    "MensagemInDB",
    "Remetente",
    "VizuClientContext",
    "SafeClientContext",
    "InternalClientContext",
    "SEED_CLIENTS",
    "get_client_by_name",
    "get_all_rag_collections",
    "TipoCliente",
    "TierCliente",
    "TipoFonte",
    "ToolCategory",
    # MCP Resources & Prompts support
    "PromptTemplate",
    "PromptTemplateCreate",
    "PromptTemplateRead",
    "PromptTemplateUpdate",
    "KnowledgeBaseConfig",
    "KnowledgeBaseConfigCreate",
    "KnowledgeBaseConfigRead",
    "KnowledgeBaseConfigUpdate",
    # SQL Schema Config (Text-to-SQL semantic context)
    "SqlTableConfig",
    "SqlTableConfigCreate",
    "SqlTableConfigRead",
    "SqlTableConfigUpdate",
    # Agent Types (shared across all agents)
    "ElicitationType",
    "ElicitationOption",
    "ElicitationRequest",
    "ElicitationResponse",
    "ToolInfo",
    "ToolExecutionResult",
    "ModelInfo",
    "AgentChatRequest",
    "AgentChatResponse",
    "ClientContextResponse",
    # HITL (Human-in-the-Loop)
    "HitlCriteriaType",
    "HitlReviewStatus",
    "HitlFeedbackType",
    "HitlCriterion",
    "HitlConfig",
    "HitlReview",
    "HitlReviewCreate",
    "HitlReviewRead",
    "HitlReviewUpdate",
    "HitlQueueStats",
    "HitlDecision",
    # Experiment Suite
    "ExperimentStatus",
    "CaseOutcome",
    "ClassificationResult",
    "TestCaseDefinition",
    "ClientVariant",
    "HitlRoutingConfig",
    "LangfuseConfig",
    "ExperimentManifest",
    "ExperimentRunSummary",
    "ExperimentProgress",
    "ExperimentRun",
    "ExperimentCase",
    # Integrations
    "IntegrationConfig",
    "IntegrationTokens",
    "OAuthTokenResponse",
    "IntegrationProvider",
]
