"""add_conversa_mensagem tables
Revision ID: 20251129_add_conversa_mensagem
Revises: 20251128_merge_heads
Create Date: 2025-11-29

Add the conversa and mensagem tables for persisting chat sessions.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251129_add_conversa_mensagem"
down_revision = "20251128_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create remetente enum
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'remetente_enum') THEN
            CREATE TYPE remetente_enum AS ENUM ('user', 'ai');
        END IF;
    END
    $$;
    """)

    # Create conversa table
    op.execute("""
    CREATE TABLE IF NOT EXISTS conversa (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id VARCHAR(255),
        cliente_final_id INTEGER,
        timestamp_inicio TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    """)

    # Create index on session_id
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_conversa_session_id ON conversa(session_id);
    """)

    # Create mensagem table
    op.execute("""
    CREATE TABLE IF NOT EXISTS mensagem (
        id SERIAL PRIMARY KEY,
        conversa_id UUID NOT NULL REFERENCES conversa(id) ON DELETE CASCADE,
        remetente remetente_enum NOT NULL,
        conteudo TEXT NOT NULL,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    """)

    # Create index on timestamp for ordering
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_mensagem_timestamp ON mensagem(timestamp);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mensagem;")
    op.execute("DROP TABLE IF EXISTS conversa;")
    op.execute("DROP TYPE IF EXISTS remetente_enum;")
