"""
SQL Schema Configuration Models

Tabela para armazenar configurações de schema SQL por cliente.
Permite definir quais tabelas estão disponíveis e metadados semânticos
para melhorar a precisão de Text-to-SQL.

Integração com MCP: @mcp.resource("sql://...") busca desta tabela.
"""

import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, Column
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as pgUUID, JSONB

if TYPE_CHECKING:
    from .cliente_vizu import ClienteVizu


class SqlTableConfig(SQLModel, table=True):
    """
    Configuração de uma tabela SQL disponível para um cliente.

    Define metadados semânticos que ajudam o LLM a gerar queries melhores:
    - description: O que esta tabela contém
    - column_descriptions: Descrição de cada coluna
    - enum_values: Valores válidos para colunas de tipo enum/categoria
    - example_queries: Exemplos de queries comuns
    """

    __tablename__ = "sql_table_config"

    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(pgUUID(as_uuid=True), primary_key=True),
    )

    cliente_vizu_id: uuid.UUID = Field(
        sa_column=Column(
            pgUUID(as_uuid=True),
            ForeignKey("cliente_vizu.id"),
            nullable=False,
            index=True,
        )
    )

    # Table identification
    table_name: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="Nome da tabela no banco (ex: 'computer_products')",
    )

    schema_name: str = Field(
        default="public",
        sa_column=Column(String(100), nullable=False),
        description="Schema do PostgreSQL (default: public)",
    )

    # Semantic metadata for LLM
    display_name: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100)),
        description="Nome amigável para exibição (ex: 'Products Catalog')",
    )

    description: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Descrição do conteúdo da tabela para o LLM",
    )

    column_descriptions: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Dict de {column_name: description} para cada coluna",
    )

    enum_values: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Dict de {column_name: [valid_values]} para colunas categóricas",
    )

    example_queries: Optional[List[dict]] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Lista de {question: sql} exemplos para few-shot learning",
    )

    # Access control
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, server_default="true"),
        description="Se esta tabela está disponível para queries",
    )

    is_primary: bool = Field(
        default=False,
        sa_column=Column(Boolean, server_default="false"),
        description="Se esta é a tabela principal do cliente (priorizada no contexto)",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False),
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, onupdate=datetime.utcnow),
    )

    # Relationship
    cliente_vizu: Optional["ClienteVizu"] = Relationship()


class SqlTableConfigCreate(SQLModel):
    """Schema para criar uma nova configuração de tabela."""

    cliente_vizu_id: uuid.UUID
    table_name: str
    schema_name: str = "public"
    display_name: Optional[str] = None
    description: Optional[str] = None
    column_descriptions: Optional[dict] = None
    enum_values: Optional[dict] = None
    example_queries: Optional[List[dict]] = None
    is_primary: bool = False


class SqlTableConfigRead(SQLModel):
    """Schema para leitura de configuração de tabela."""

    id: uuid.UUID
    cliente_vizu_id: uuid.UUID
    table_name: str
    schema_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    column_descriptions: Optional[dict] = None
    enum_values: Optional[dict] = None
    example_queries: Optional[List[dict]] = None
    is_active: bool
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class SqlTableConfigUpdate(SQLModel):
    """Schema para atualizar uma configuração de tabela."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    column_descriptions: Optional[dict] = None
    enum_values: Optional[dict] = None
    example_queries: Optional[List[dict]] = None
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
