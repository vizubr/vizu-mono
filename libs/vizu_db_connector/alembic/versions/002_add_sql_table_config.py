"""Add sql_table_config table for Text-to-SQL semantic context

Revision ID: 002_add_sql_table_config
Revises: 001_consolidated_initial_schema
Create Date: 2025-12-09

This migration adds the sql_table_config table which stores semantic metadata
for tables available to Text-to-SQL queries. This helps the LLM generate more
accurate SQL by providing:
- Table and column descriptions
- Valid enum values (critical for case-sensitivity)
- Example queries for few-shot learning
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002_add_sql_table_config"
down_revision = "001_consolidated_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sql_table_config table."""
    op.create_table(
        'sql_table_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cliente_vizu_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('schema_name', sa.String(length=100), nullable=False, server_default='public'),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('column_descriptions', postgresql.JSONB(), nullable=True),
        sa.Column('enum_values', postgresql.JSONB(), nullable=True),
        sa.Column('example_queries', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['cliente_vizu_id'], ['cliente_vizu.id'], ondelete='CASCADE'),
    )

    # Create unique constraint for table_name per client
    op.create_unique_constraint(
        'uq_sql_table_config_client_table',
        'sql_table_config',
        ['cliente_vizu_id', 'table_name', 'schema_name']
    )


def downgrade() -> None:
    """Drop sql_table_config table."""
    op.drop_constraint('uq_sql_table_config_client_table', 'sql_table_config', type_='unique')
    op.drop_table('sql_table_config')
