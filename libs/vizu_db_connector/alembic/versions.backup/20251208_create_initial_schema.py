"""Create initial schema from vizu_models

Revision ID: 20251208_create_initial_schema
Revises: e60514203590
Create Date: 2025-12-08

This migration creates all core tables from vizu_models.
It replaces the empty initial migration to provide a complete schema foundation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20251208_create_initial_schema"
down_revision = "e60514203590"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM types first (create_type=True tells SQLAlchemy to CREATE TYPE if it doesn't exist)
    tipo_cliente_enum = sa.Enum('INTERNAL', 'B2B', 'B2C', 'PARTNER', name='tipo_cliente_enum')
    tier_cliente_enum = sa.Enum('BASIC', 'SME', 'ENTERPRISE', 'CUSTOM', name='tier_cliente_enum')
    
    # Bind them to the migration context so they're created
    tipo_cliente_enum.create(op.get_bind(), checkfirst=True)
    tier_cliente_enum.create(op.get_bind(), checkfirst=True)

    # Create cliente_vizu table
    op.create_table(
        'cliente_vizu',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('nome_empresa', sa.String(length=255), nullable=False),
        sa.Column('tipo_cliente', sa.Enum('INTERNAL', 'B2B', 'B2C', 'PARTNER', name='tipo_cliente_enum', native_enum=False), nullable=False),
        sa.Column('tier', sa.Enum('BASIC', 'SME', 'ENTERPRISE', 'CUSTOM', name='tier_cliente_enum', native_enum=False), nullable=False),
        sa.Column('api_key', sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column('horario_funcionamento', postgresql.JSON(), nullable=True),
        sa.Column('prompt_base', sa.Text(), nullable=True),
        sa.Column('enabled_tools', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('ferramenta_rag_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_sql_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_agendamento_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('collection_rag', sa.String(), nullable=True),
    )

    # Create fonte_de_dados table
    op.create_table(
        'fonte_de_dados',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('nome_fonte', sa.String(length=255), nullable=False),
        sa.Column('tipo_fonte', sa.String(length=100), nullable=False),
        sa.Column('config', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ),
    )

    # Create credencial_servico_externo table
    op.create_table(
        'credencial_servico_externo',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('servico', sa.String(length=100), nullable=False),
        sa.Column('credenciais', postgresql.JSON(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ),
    )

    # Create cliente_final table
    op.create_table(
        'cliente_final',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('nome', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('telefone', sa.String(length=20), nullable=True),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ),
    )

    # Create conversa table
    op.create_table(
        'conversa',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cliente_final_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=False, index=True),
        sa.Column('titulo', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ),
        sa.ForeignKeyConstraint(['cliente_final_id'], ['cliente_final.id'], ),
    )

    # Create mensagem table
    op.create_table(
        'mensagem',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversa_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['conversa_id'], ['conversa.id'], ),
    )

    # Create configuracao_negocio table
    op.create_table(
        'configuracao_negocio',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('horario_funcionamento', postgresql.JSON(), nullable=True),
        sa.Column('prompt_base', sa.Text(), nullable=True),
        sa.Column('ferramenta_rag_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_sql_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ferramenta_agendamento_habilitada', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('collection_rag', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ),
    )

    # NOTE: Do NOT manually create alembic_version table.
    # Alembic will create it automatically with the correct version_num_type.


def downgrade() -> None:
    op.drop_table('alembic_version', if_exists=True)
    op.drop_table('configuracao_negocio', if_exists=True)
    op.drop_table('mensagem', if_exists=True)
    op.drop_table('conversa', if_exists=True)
    op.drop_table('cliente_final', if_exists=True)
    op.drop_table('credencial_servico_externo', if_exists=True)
    op.drop_table('fonte_de_dados', if_exists=True)
    op.drop_table('cliente_vizu', if_exists=True)
    
    op.execute('DROP TYPE tier_cliente_enum;')
    op.execute('DROP TYPE tipo_cliente_enum;')
