import logging
from typing import Optional
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables.base import Runnable
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import os

# Dependências de outras libs Vizu
from vizu_models.vizu_client_context import VizuClientContext

logger = logging.getLogger(__name__)

# ============================================================================
# ENGINE COMPARTILHADA (SINGLETON)
# ============================================================================
# Uma única engine para todos os clientes. O isolamento é garantido pelo RLS.
#
# NOTA: Este módulo usa SQLAlchemy porque o LangChain SQL Agent requer
# uma conexão direta ao PostgreSQL para introspecção e execução de queries.
#
# Para operações CRUD simples, use vizu_supabase_client que usa a API REST
# do Supabase e não tem problemas de DNS/conectividade.
#
# Ambientes:
# - LOCAL: DATABASE_URL postgresql://user:password@localhost:5432/vizu_db
# - DOCKER: DATABASE_URL postgresql://user:password@postgres:5432/vizu_db
# - SUPABASE: Requer conexão direta (pode ter issues de DNS)

_shared_engine: Optional[Engine] = None


def _get_database_url() -> str:
    """
    Obtém a URL de conexão do banco de dados.

    Prioridade:
    1. DATABASE_URL (conexão direta PostgreSQL)
    2. Construção a partir de variáveis POSTGRES_*

    Para Supabase, se houver problemas de DNS com a URL direta,
    considere usar o Supabase SDK para CRUD e reservar SQLAlchemy
    apenas para o SQL Agent em ambiente local/Docker.
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    # Fallback: construir a URL a partir de variáveis individuais
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_name = os.getenv("POSTGRES_DB", "postgres")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


def get_shared_engine() -> Engine:
    """
    Retorna a engine compartilhada (singleton).
    Cria a engine na primeira chamada.
    """
    global _shared_engine

    if _shared_engine is None:
        db_url = _get_database_url()
        logger.info("Criando engine SQL compartilhada...")

        _shared_engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=10,  # Conexões mantidas no pool
            max_overflow=20,  # Conexões extras em pico
            pool_recycle=300,  # Recicla conexões a cada 5 min
            pool_pre_ping=True,  # Verifica conexão antes de usar
            echo=False,  # Desabilita log de queries (usar logging próprio)
        )

        logger.info("Engine SQL compartilhada criada com sucesso.")

    return _shared_engine


def close_shared_engine() -> None:
    """Fecha a engine compartilhada (para shutdown graceful)."""
    global _shared_engine
    if _shared_engine:
        _shared_engine.dispose()
        _shared_engine = None
        logger.info("Engine SQL compartilhada fechada.")


# ============================================================================
# RLS CONTEXT WRAPPER
# ============================================================================


class RLSContextDatabase(SQLDatabase):
    """
    Wrapper do SQLDatabase que seta o contexto RLS antes de cada operação.
    Garante isolamento multi-tenant usando Row Level Security do PostgreSQL.
    """

    def __init__(self, engine: Engine, cliente_id: str, **kwargs):
        super().__init__(engine=engine, **kwargs)
        self._cliente_id = cliente_id

    def _set_rls_context(self, connection):
        """Seta o contexto RLS na conexão."""
        try:
            connection.execute(
                text("SELECT set_config('app.current_cliente_id', :cliente_id, true)"),
                {"cliente_id": self._cliente_id},
            )
            logger.debug(f"RLS context set for cliente_id: {self._cliente_id}")
        except Exception as e:
            logger.warning(f"Could not set RLS context: {e}")

    def run(
        self,
        command: str,
        fetch: str = "all",
        include_columns: bool = False,
        *,
        parameters: Optional[dict] = None,
        execution_options: Optional[dict] = None,
    ) -> str:
        """Executa query com contexto RLS.

        Args:
            command: SQL command to execute
            fetch: "all", "one", or "cursor"
            include_columns: Whether to include column names
            parameters: SQL parameters for parameterized queries
            execution_options: SQLAlchemy execution options

        Returns:
            Query results as string
        """
        from sqlalchemy import text as sa_text

        if parameters is None:
            parameters = {}
        if execution_options is None:
            execution_options = {}

        with self._engine.connect() as connection:
            # Set RLS context first, then commit to ensure it's active
            connection.execute(
                sa_text("SELECT set_config('app.current_cliente_id', :cliente_id, false)"),
                {"cliente_id": self._cliente_id},
            )
            connection.commit()

            # Execute the query in a new transaction
            cursor = connection.execute(
                sa_text(command),
                parameters,
            )

            if fetch == "cursor":
                return cursor

            if fetch == "one":
                result = cursor.fetchone()
                if result is None:
                    return ""
                if include_columns:
                    return str(dict(zip(cursor.keys(), result)))
                return str(result)

            # fetch == "all"
            results = cursor.fetchall()
            if not results:
                return ""

            if include_columns:
                columns = list(cursor.keys())
                return str([dict(zip(columns, row)) for row in results])

            return str(results)

    def get_table_info(self, table_names: Optional[list[str]] = None) -> str:
        """Obtém info das tabelas com contexto RLS."""
        # Para metadados, não precisa de RLS (é schema, não dados)
        return super().get_table_info(table_names)


# ============================================================================
# LEGACY: SQL AGENT FACTORY
# ============================================================================
# NOTE: This function is DEPRECATED as of the Text-to-SQL refactor.
# sql_module.py now uses a simplified approach with direct LLM call + SQL execution,
# which works with models that don't support ReAct or function-calling formats.
# This function remains for backwards compatibility and test coverage.
# ============================================================================


def create_sql_agent_runnable(
    contexto: VizuClientContext,
    llm: BaseChatModel,
    llm_fast: Optional[BaseChatModel] = None,
    tabelas_incluidas: Optional[list[str]] = None,
) -> Optional[Runnable]:
    """
    Factory para criar um Agente SQL com isolamento via RLS.

    Usa a nova API create_agent do LangChain v1.0+ com SQLDatabaseToolkit.
    Garante isolamento configurando o contexto RLS antes de cada query.

    Args:
        contexto: O VizuClientContext completo.
        llm: O LLM principal para execução do agente (obrigatório).
        llm_fast: (Opcional) LLM rápido para classificação/introspecção.
        tabelas_incluidas: (Opcional) Lista de tabelas a incluir.

    Returns:
        Uma instância de 'Runnable' (Agente SQL) ou None se desabilitado.

    Raises:
        ValueError: Se llm for None.
    """

    # --- 0. Validação do LLM (obrigatório) ---
    if llm is None:
        logger.error(
            f"LLM não fornecido para create_sql_agent_runnable do cliente {contexto.id}. "
            "Utilize get_model() do vizu_llm_service para obter um LLM."
        )
        raise ValueError("llm é obrigatório para create_sql_agent_runnable")

    # --- 1. Validação de Permissão ---
    if not contexto.ferramenta_sql_habilitada:
        logger.warning(
            f"Tentativa de criar agente SQL para cliente {contexto.id} - SQL desabilitado."
        )
        return None

    # --- 2. Obter Engine Compartilhada ---
    engine = get_shared_engine()
    cliente_id = str(contexto.id)

    logger.info(f"Construindo componentes SQL para cliente {contexto.id}")

    # --- 3. Criar SQLDatabase com RLS ---
    db = RLSContextDatabase(
        engine=engine, cliente_id=cliente_id, include_tables=tabelas_incluidas
    )

    # --- 4. Criação do Agente usando create_sql_agent (langchain_community) ---
    logger.info(f"Instanciando Agente SQL para {contexto.id}...")

    from langchain_community.agent_toolkits import create_sql_agent

    # System prompt - simple and direct in English for better model compliance
    prefix = """You are an expert SQL assistant. Your task is to answer questions about a database.

IMPORTANT RULES:
1. FIRST, always list the available tables using sql_db_list_tables
2. THEN, get the schema of relevant tables using sql_db_schema
3. THEN, write and execute your SQL query using sql_db_query
4. ALWAYS execute queries to get real data - NEVER guess or make up numbers
5. Return the EXACT results from the query

Available tools:
- sql_db_list_tables: Lists all tables in the database
- sql_db_schema: Shows the schema of specified tables
- sql_db_query: Executes a SQL SELECT query and returns results
- sql_db_query_checker: Validates SQL syntax before execution

NEVER make up data. ALWAYS run the query and report the actual results."""

    suffix = """Begin! Remember to ALWAYS execute queries to get real data.

Question: {input}
{agent_scratchpad}"""

    # Criar agente SQL usando a API do langchain_community
    agent_executor_kwargs = {
        "handle_parsing_errors": True,
        "return_intermediate_steps": True,
    }

    # Force openai-tools agent type since it uses tool binding
    # which works better with most models than ReAct text parsing
    try:
        agent = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="openai-tools",  # Use tool binding, not ReAct
            prefix=prefix,
            suffix=suffix,
            verbose=True,
            max_iterations=10,
            agent_executor_kwargs=agent_executor_kwargs,
        )
        logger.info(f"Agente SQL criado com openai-tools para {contexto.id}.")
    except Exception as e:
        # If openai-tools fails, try zero-shot-react-description as last resort
        logger.warning(f"openai-tools falhou ({e}), tentando zero-shot-react-description...")
        agent = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="zero-shot-react-description",
            prefix=prefix,
            suffix=suffix,
            verbose=True,
            max_iterations=10,
            agent_executor_kwargs=agent_executor_kwargs,
        )
        logger.info(f"Agente SQL criado com zero-shot-react-description para {contexto.id}.")

    return agent
