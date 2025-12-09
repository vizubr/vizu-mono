"""create integration_configs and integration_tokens tables
Revision ID: 20251202_add_integration_tables
Revises: 20251201_add_mcp_tables
Create Date: 2025-12-02
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251202_add_integration_tables"
down_revision = "20251201_add_mcp_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Integration configuration table
    op.execute("""
    CREATE TABLE IF NOT EXISTS integration_configs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        cliente_vizu_id UUID NOT NULL REFERENCES cliente_vizu(id) ON DELETE CASCADE,
        provider VARCHAR(50) NOT NULL,
        config_type VARCHAR(50) NOT NULL,

        client_id_encrypted TEXT NOT NULL,
        client_secret_encrypted TEXT NOT NULL,

        redirect_uri VARCHAR(500) NOT NULL,
        scopes JSONB NOT NULL,

        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now(),

        CONSTRAINT uq_integration_config_cliente_provider_type UNIQUE (cliente_vizu_id, provider, config_type)
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS integration_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        cliente_vizu_id UUID NOT NULL REFERENCES cliente_vizu(id) ON DELETE CASCADE,
        provider VARCHAR(50) NOT NULL,

        access_token_encrypted TEXT NOT NULL,
        refresh_token_encrypted TEXT,
        token_type VARCHAR(50),
        expires_at TIMESTAMP,
        scopes JSONB NOT NULL,
        metadata JSONB,

        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now(),

        CONSTRAINT uq_integration_tokens_cliente_provider UNIQUE (cliente_vizu_id, provider)
    );
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_integration_tokens_cliente_provider
    ON integration_tokens (cliente_vizu_id, provider);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_integration_tokens_cliente_provider;")
    op.execute("DROP TABLE IF EXISTS integration_tokens;")
    op.execute("DROP TABLE IF EXISTS integration_configs;")
