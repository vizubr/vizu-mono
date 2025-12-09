"""add_server_defaults
Revision ID: 20251126_add_server_defaults
Revises: 97f287628115
Create Date: 2025-11-26

Add server-side defaults for UUIDs and boolean flags to ensure inserts
work when clients don't provide values. Also enable `pgcrypto` extension
for `gen_random_uuid()` on Postgres-compatible hosts (Supabase supports it).
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251126_add_server_defaults"
down_revision = "97f287628115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgcrypto is available for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # Set server defaults for cliente_vizu.id and api_key
    op.execute(
        "ALTER TABLE cliente_vizu ALTER COLUMN id SET DEFAULT gen_random_uuid();"
    )
    op.execute(
        "ALTER TABLE cliente_vizu ALTER COLUMN api_key SET DEFAULT gen_random_uuid()::text;"
    )

    # Ensure boolean flags in configuracao_negocio have defaults
    op.execute(
        "ALTER TABLE configuracao_negocio ALTER COLUMN ferramenta_rag_habilitada SET DEFAULT false;"
    )
    op.execute(
        "ALTER TABLE configuracao_negocio ALTER COLUMN ferramenta_sql_habilitada SET DEFAULT false;"
    )
    op.execute(
        "ALTER TABLE configuracao_negocio ALTER COLUMN ferramenta_agendamento_habilitada SET DEFAULT false;"
    )


def downgrade() -> None:
    # Revert defaults (keep extension)
    op.execute("ALTER TABLE cliente_vizu ALTER COLUMN id DROP DEFAULT;")
    op.execute("ALTER TABLE cliente_vizu ALTER COLUMN api_key DROP DEFAULT;")

    op.execute(
        "ALTER TABLE configuracao_negocio ALTER COLUMN ferramenta_rag_habilitada DROP DEFAULT;"
    )
    op.execute(
        "ALTER TABLE configuracao_negocio ALTER COLUMN ferramenta_sql_habilitada DROP DEFAULT;"
    )
    op.execute(
        "ALTER TABLE configuracao_negocio ALTER COLUMN ferramenta_agendamento_habilitada DROP DEFAULT;"
    )
