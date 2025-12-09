"""Consolidated initial schema from vizu_models

Revision ID: 001_consolidated_initial_schema
Revises:
Create Date: 2025-12-08 12:00:00.000000

This migration creates the complete database schema from vizu_models in a single,
clean migration. It replaces all historical branches and development migrations.

All tables are created together to ensure proper foreign key relationships.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_consolidated_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables from vizu_models"""

    # Create ENUM types - must match vizu_models definitions
    op.execute("""
        CREATE TYPE tipo_cliente_enum AS ENUM ('B2B', 'B2C', 'EXTERNO');
    """)

    op.execute("""
        CREATE TYPE tier_cliente_enum AS ENUM ('FREE', 'BASIC', 'SME', 'PREMIUM', 'ENTERPRISE');
    """)

    op.execute("""
        CREATE TYPE remetente_enum AS ENUM ('user', 'ai');
    """)

    # ========== CORE TABLES ==========

    # cliente_vizu - main customer entity
    op.create_table(
        'cliente_vizu',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('nome_empresa', sa.String(length=255), nullable=False),
        sa.Column('tipo_cliente', sa.Enum('B2B', 'B2C', 'EXTERNO', name='tipo_cliente_enum', native_enum=False), nullable=False),
        sa.Column('tier', sa.Enum('FREE', 'BASIC', 'SME', 'PREMIUM', 'ENTERPRISE', name='tier_cliente_enum', native_enum=False), nullable=False),
        sa.Column('api_key', sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column('horario_funcionamento', postgresql.JSON(), nullable=True),
        sa.Column('prompt_base', sa.Text(), nullable=True),
        sa.Column('enabled_tools', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('ferramenta_rag_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_sql_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_agendamento_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('collection_rag', sa.String(), nullable=True),
    )

    # fonte_de_dados - data sources associated with clients
    op.create_table(
        'fonte_de_dados',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('nome_fonte', sa.String(length=255), nullable=False),
        sa.Column('tipo_fonte', sa.String(length=100), nullable=False),
        sa.Column('config', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
    )

    # credencial_servico_externo - external service credentials
    op.create_table(
        'credencial_servico_externo',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('servico', sa.String(length=100), nullable=False),
        sa.Column('credenciais', postgresql.JSON(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
    )

    # cliente_final - end users/customers of the client
    op.create_table(
        'cliente_final',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('nome', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True, index=True),
        sa.Column('telefone', sa.String(length=20), nullable=True),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
    )

    # ========== CONVERSATION TABLES ==========

    # conversa - conversations between agents and clients
    op.create_table(
        'conversa',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('cliente_final_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('session_id', sa.String(length=255), nullable=True, index=True),
        sa.Column('timestamp_inicio', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cliente_final_id'], ['cliente_final.id'], ondelete='SET NULL'),
    )

    # mensagem - individual messages in conversations
    op.create_table(
        'mensagem',
        sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
        sa.Column('conversa_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('remetente', sa.Enum('user', 'ai', name='remetente_enum', native_enum=False), nullable=False),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.ForeignKeyConstraint(['conversa_id'], ['conversa.id'], ondelete='CASCADE'),
    )

    # ========== CONFIGURATION TABLES ==========

    # configuracao_negocio - business configuration (legacy, kept for backward compatibility)
    op.create_table(
        'configuracao_negocio',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column('horario_funcionamento', postgresql.JSON(), nullable=True),
        sa.Column('prompt_base', sa.Text(), nullable=True),
        sa.Column('ferramenta_rag_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_sql_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_agendamento_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('collection_rag', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
    )

    # ========== MCP / TOOL INTEGRATION TABLES ==========

    # mcp_server - registered MCP servers
    op.create_table(
        'mcp_server',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('config', postgresql.JSON(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # mcp_tool_schema - tool schemas from MCP servers
    op.create_table(
        'mcp_tool_schema',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('mcp_server_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('tool_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('input_schema', postgresql.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['mcp_server_id'], ['mcp_server.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('mcp_server_id', 'tool_name', name='uq_mcp_server_tool_name'),
    )

    # prompt_template - versionized system prompts (global or per-client)
    op.create_table(
        'prompt_template',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('variables', postgresql.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('name', 'version', 'cliente_vizu_id', name='uq_prompt_name_version_client'),
    )

    # ========== HITL (Human-in-the-loop) TABLES ==========

    # hitl_review - human-in-the-loop reviews
    op.create_table(
        'hitl_review',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('conversa_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('tool_call_id', sa.String(length=255), nullable=True, index=True),
        sa.Column('tool_name', sa.String(length=255), nullable=False),
        sa.Column('input_data', postgresql.JSON(), nullable=False),
        sa.Column('output_data', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversa_id'], ['conversa.id'], ondelete='SET NULL'),
    )

    # ========== EXPERIMENT / EVALUATION TABLES ==========

    # experiment - A/B testing and experiments
    op.create_table(
        'experiment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('variant_a', postgresql.JSON(), nullable=False),
        sa.Column('variant_b', postgresql.JSON(), nullable=False),
        sa.Column('config', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
    )

    # ========== INTEGRATION TABLES ==========

    # integration_connection - external service integrations
    op.create_table(
        'integration_connection',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('service_type', sa.String(length=100), nullable=False),
        sa.Column('config', postgresql.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
    )

    # ========== INDEXES FOR COMMON QUERIES ==========

    op.create_index('ix_fonte_de_dados_cliente_vizu', 'fonte_de_dados', ['cliente_vizu_id'])
    op.create_index('ix_credencial_servico_cliente_vizu', 'credencial_servico_externo', ['cliente_vizu_id'])
    op.create_index('ix_cliente_final_cliente_vizu', 'cliente_final', ['cliente_vizu_id'])
    op.create_index('ix_conversa_cliente_vizu', 'conversa', ['cliente_vizu_id'])
    # Note: session_id index is already created by the table definition
    op.create_index('ix_mensagem_conversa', 'mensagem', ['conversa_id'])
    op.create_index('ix_hitl_review_cliente_vizu', 'hitl_review', ['cliente_vizu_id'])
    op.create_index('ix_experiment_cliente_vizu', 'experiment', ['cliente_vizu_id'])
    op.create_index('ix_integration_connection_cliente_vizu', 'integration_connection', ['cliente_vizu_id'])
def downgrade() -> None:
    """Drop all tables and types"""

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('integration_connection', if_exists=True)
    op.drop_table('experiment', if_exists=True)
    op.drop_table('hitl_review', if_exists=True)
    op.drop_table('mcp_tool_schema', if_exists=True)
    op.drop_table('mcp_server', if_exists=True)
    op.drop_table('configuracao_negocio', if_exists=True)
    op.drop_table('mensagem', if_exists=True)
    op.drop_table('conversa', if_exists=True)
    op.drop_table('cliente_final', if_exists=True)
    op.drop_table('credencial_servico_externo', if_exists=True)
    op.drop_table('fonte_de_dados', if_exists=True)
    op.drop_table('cliente_vizu', if_exists=True)

    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS tier_cliente_enum;')
    op.execute('DROP TYPE IF EXISTS tipo_cliente_enum;')
