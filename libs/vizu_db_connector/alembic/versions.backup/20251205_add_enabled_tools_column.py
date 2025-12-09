"""add_enabled_tools_column and tier updates

Revision ID: 20251205_add_enabled_tools
Revises: 20251215_add_experiment_tables
Create Date: 2025-12-05

PHASE 1: Dynamic Tool Allocation
- Add enabled_tools JSONB column to cliente_vizu
- Backfill enabled_tools from legacy boolean flags
- Keep legacy columns for backward compatibility

This migration replaces 3 boolean tool flags with a single dynamic list:
- ferramenta_rag_habilitada -> 'executar_rag_cliente' in enabled_tools
- ferramenta_sql_habilitada -> 'executar_sql_agent' in enabled_tools
- ferramenta_agendamento_habilitada -> 'agendar_consulta' in enabled_tools
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20251205_add_enabled_tools"
down_revision = "20251215_add_experiment_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # Step 1: Add enabled_tools column to cliente_vizu
    # ============================================================
    op.execute("""
    ALTER TABLE cliente_vizu
    ADD COLUMN IF NOT EXISTS enabled_tools JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)

    # ============================================================
    # Step 2: Backfill enabled_tools from legacy boolean flags
    # Each client gets a list of enabled tools based on their flags
    # ============================================================
    op.execute("""
    UPDATE cliente_vizu
    SET enabled_tools = (
        SELECT COALESCE(jsonb_agg(tool_name), '[]'::jsonb)
        FROM (
            SELECT 'executar_rag_cliente' as tool_name
            WHERE ferramenta_rag_habilitada = true
            UNION ALL
            SELECT 'executar_sql_agent' as tool_name
            WHERE ferramenta_sql_habilitada = true
            UNION ALL
            SELECT 'agendar_consulta' as tool_name
            WHERE ferramenta_agendamento_habilitada = true
        ) AS tools
    )
    WHERE enabled_tools = '[]'::jsonb;
    """)

    # ============================================================
    # Step 3: Add index on enabled_tools for GIN queries
    # Enables efficient queries like: enabled_tools @> '["executar_rag_cliente"]'
    # ============================================================
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_cliente_vizu_enabled_tools
    ON cliente_vizu USING GIN (enabled_tools);
    """)

    # ============================================================
    # Step 4: Add comment on legacy columns marking them deprecated
    # ============================================================
    op.execute("""
    COMMENT ON COLUMN cliente_vizu.ferramenta_rag_habilitada IS
    'DEPRECATED: Use enabled_tools instead. Will be removed in v1.1.';
    """)
    op.execute("""
    COMMENT ON COLUMN cliente_vizu.ferramenta_sql_habilitada IS
    'DEPRECATED: Use enabled_tools instead. Will be removed in v1.1.';
    """)
    op.execute("""
    COMMENT ON COLUMN cliente_vizu.ferramenta_agendamento_habilitada IS
    'DEPRECATED: Use enabled_tools instead. Will be removed in v1.1.';
    """)

    # ============================================================
    # Step 5: Create helper function for tool management
    # ============================================================
    op.execute("""
    CREATE OR REPLACE FUNCTION add_tool_to_client(
        p_cliente_id UUID,
        p_tool_name TEXT
    ) RETURNS VOID AS $$
    BEGIN
        UPDATE cliente_vizu
        SET enabled_tools = enabled_tools || to_jsonb(p_tool_name)
        WHERE id = p_cliente_id
        AND NOT enabled_tools ? p_tool_name;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION remove_tool_from_client(
        p_cliente_id UUID,
        p_tool_name TEXT
    ) RETURNS VOID AS $$
    BEGIN
        UPDATE cliente_vizu
        SET enabled_tools = enabled_tools - p_tool_name
        WHERE id = p_cliente_id;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION client_has_tool(
        p_cliente_id UUID,
        p_tool_name TEXT
    ) RETURNS BOOLEAN AS $$
    DECLARE
        has_tool BOOLEAN;
    BEGIN
        SELECT enabled_tools ? p_tool_name INTO has_tool
        FROM cliente_vizu
        WHERE id = p_cliente_id;
        RETURN COALESCE(has_tool, false);
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Remove helper functions
    op.execute("DROP FUNCTION IF EXISTS client_has_tool(UUID, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS remove_tool_from_client(UUID, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS add_tool_to_client(UUID, TEXT);")

    # Remove index
    op.execute("DROP INDEX IF EXISTS ix_cliente_vizu_enabled_tools;")

    # Remove comments
    op.execute("COMMENT ON COLUMN cliente_vizu.ferramenta_rag_habilitada IS NULL;")
    op.execute("COMMENT ON COLUMN cliente_vizu.ferramenta_sql_habilitada IS NULL;")
    op.execute("COMMENT ON COLUMN cliente_vizu.ferramenta_agendamento_habilitada IS NULL;")

    # Remove column
    op.execute("ALTER TABLE cliente_vizu DROP COLUMN IF EXISTS enabled_tools;")
