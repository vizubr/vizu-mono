"""merge_configuracao_into_cliente_vizu
Revision ID: 20251128_merge_cfg
Revises: 20251126_add_server_defaults
Create Date: 2025-11-28

Add configuracao_negocio fields to cliente_vizu and copy existing data.
This is a safe first-step migration: it adds columns and copies data but does
not drop the legacy `configuracao_negocio` table. A follow-up migration should
remove the legacy table after the application has been updated.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251128_merge_cfg"
down_revision = "20251126_add_server_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to cliente_vizu using IF NOT EXISTS to make migration idempotent
    op.execute("""
        ALTER TABLE IF EXISTS public.cliente_vizu
            ADD COLUMN IF NOT EXISTS horario_funcionamento jsonb;
        """)
    op.execute("""
        ALTER TABLE IF EXISTS public.cliente_vizu
            ADD COLUMN IF NOT EXISTS prompt_base text;
        """)
    op.execute("""
        ALTER TABLE IF EXISTS public.cliente_vizu
            ADD COLUMN IF NOT EXISTS ferramenta_rag_habilitada boolean DEFAULT false NOT NULL;
        """)
    op.execute("""
        ALTER TABLE IF EXISTS public.cliente_vizu
            ADD COLUMN IF NOT EXISTS ferramenta_sql_habilitada boolean DEFAULT false NOT NULL;
        """)
    op.execute("""
        ALTER TABLE IF EXISTS public.cliente_vizu
            ADD COLUMN IF NOT EXISTS ferramenta_agendamento_habilitada boolean DEFAULT false NOT NULL;
        """)
    op.execute("""
        ALTER TABLE IF EXISTS public.cliente_vizu
            ADD COLUMN IF NOT EXISTS collection_rag text;
        """)

    # Copy existing data from configuracao_negocio (if the table exists)
    # Use DO block to guard if the source table/column may be missing
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'configuracao_negocio') THEN
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'configuracao_negocio' AND column_name = 'collection_rag') THEN
                    UPDATE public.cliente_vizu cv
                    SET horario_funcionamento = cn.horario_funcionamento,
                        prompt_base = cn.prompt_base,
                        ferramenta_rag_habilitada = COALESCE(cn.ferramenta_rag_habilitada, false),
                        ferramenta_sql_habilitada = COALESCE(cn.ferramenta_sql_habilitada, false),
                        ferramenta_agendamento_habilitada = COALESCE(cn.ferramenta_agendamento_habilitada, false),
                        collection_rag = cn.collection_rag
                    FROM public.configuracao_negocio cn
                    WHERE cn.cliente_vizu_id = cv.id;
                ELSE
                    UPDATE public.cliente_vizu cv
                    SET horario_funcionamento = cn.horario_funcionamento,
                        prompt_base = cn.prompt_base,
                        ferramenta_rag_habilitada = COALESCE(cn.ferramenta_rag_habilitada, false),
                        ferramenta_sql_habilitada = COALESCE(cn.ferramenta_sql_habilitada, false),
                        ferramenta_agendamento_habilitada = COALESCE(cn.ferramenta_agendamento_habilitada, false)
                    FROM public.configuracao_negocio cn
                    WHERE cn.cliente_vizu_id = cv.id;
                END IF;
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
    # Remove added columns
    op.drop_column("cliente_vizu", "collection_rag")
    op.drop_column("cliente_vizu", "ferramenta_agendamento_habilitada")
    op.drop_column("cliente_vizu", "ferramenta_sql_habilitada")
    op.drop_column("cliente_vizu", "ferramenta_rag_habilitada")
    op.drop_column("cliente_vizu", "prompt_base")
    op.drop_column("cliente_vizu", "horario_funcionamento")
