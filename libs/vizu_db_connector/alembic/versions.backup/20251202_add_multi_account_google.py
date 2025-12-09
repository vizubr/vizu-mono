"""Add multi-account support for Google integration

Adds account_email column to integration_tokens to allow multiple Google accounts
per cliente. Updates unique constraint from (cliente_vizu_id, provider) to
(cliente_vizu_id, provider, account_email).

Revision ID: 20251202_add_multi_account_google
Revises: 20251202_add_integration_tables
Create Date: 2025-12-02
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251202_add_multi_account_google"
down_revision = "20251202_add_integration_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add account_email column for multi-account support
    op.execute("""
    ALTER TABLE integration_tokens
    ADD COLUMN IF NOT EXISTS account_email VARCHAR(320);
    """)

    # Add account_name for display purposes (e.g., "Personal", "Work")
    op.execute("""
    ALTER TABLE integration_tokens
    ADD COLUMN IF NOT EXISTS account_name VARCHAR(100);
    """)

    # Add is_default flag to mark the primary account
    op.execute("""
    ALTER TABLE integration_tokens
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT false;
    """)

    # Drop the old unique constraint
    op.execute("""
    ALTER TABLE integration_tokens
    DROP CONSTRAINT IF EXISTS uq_integration_tokens_cliente_provider;
    """)

    # Create new unique constraint including account_email
    op.execute("""
    ALTER TABLE integration_tokens
    ADD CONSTRAINT uq_integration_tokens_cliente_provider_account
    UNIQUE (cliente_vizu_id, provider, account_email);
    """)

    # Update existing rows to have a placeholder email if null
    # This ensures we don't have constraint violations
    op.execute("""
    UPDATE integration_tokens
    SET account_email = 'default@unknown.com',
        account_name = 'Primary Account',
        is_default = true
    WHERE account_email IS NULL;
    """)

    # Make account_email NOT NULL after backfill
    op.execute("""
    ALTER TABLE integration_tokens
    ALTER COLUMN account_email SET NOT NULL;
    """)

    # Update the index for better query performance
    op.execute("""
    DROP INDEX IF EXISTS idx_integration_tokens_cliente_provider;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_integration_tokens_cliente_provider_email
    ON integration_tokens (cliente_vizu_id, provider, account_email);
    """)

    # Add partial unique index to ensure only one default per cliente/provider
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_integration_tokens_default
    ON integration_tokens (cliente_vizu_id, provider)
    WHERE is_default = true;
    """)


def downgrade() -> None:
    # Remove the partial unique index
    op.execute("DROP INDEX IF EXISTS idx_integration_tokens_default;")

    # Remove the new index
    op.execute("DROP INDEX IF EXISTS idx_integration_tokens_cliente_provider_email;")

    # Drop the new constraint
    op.execute("""
    ALTER TABLE integration_tokens
    DROP CONSTRAINT IF EXISTS uq_integration_tokens_cliente_provider_account;
    """)

    # Restore original constraint (may fail if multiple accounts exist)
    op.execute("""
    ALTER TABLE integration_tokens
    ADD CONSTRAINT uq_integration_tokens_cliente_provider
    UNIQUE (cliente_vizu_id, provider);
    """)

    # Restore original index
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_integration_tokens_cliente_provider
    ON integration_tokens (cliente_vizu_id, provider);
    """)

    # Remove new columns
    op.execute("ALTER TABLE integration_tokens DROP COLUMN IF EXISTS is_default;")
    op.execute("ALTER TABLE integration_tokens DROP COLUMN IF EXISTS account_name;")
    op.execute("ALTER TABLE integration_tokens DROP COLUMN IF EXISTS account_email;")
