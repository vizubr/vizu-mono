"""add_rls_security - Row Level Security for multi-tenant isolation

Revision ID: 20251130_add_rls_security
Revises: 20251129_add_conversa_mensagem
Create Date: 2025-11-30

This migration:
1. Adds cliente_vizu_id FK to conversa table
2. Enables RLS on all tenant-specific tables
3. Creates security policies ensuring clients only access their own data
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251130_add_rls_security"
down_revision = "20251129_add_conversa_mensagem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # 1. ADD cliente_vizu_id TO conversa TABLE
    # =========================================================================

    # Add the foreign key column
    op.execute("""
    ALTER TABLE conversa
    ADD COLUMN IF NOT EXISTS cliente_vizu_id UUID REFERENCES cliente_vizu(id) ON DELETE CASCADE;
    """)

    # Create index for performance
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_conversa_cliente_vizu_id ON conversa(cliente_vizu_id);
    """)

    # =========================================================================
    # 2. ENABLE ROW LEVEL SECURITY (RLS)
    # =========================================================================

    # Enable RLS on cliente_vizu (main tenant table)
    op.execute("ALTER TABLE cliente_vizu ENABLE ROW LEVEL SECURITY;")

    # Enable RLS on conversa (chat sessions)
    op.execute("ALTER TABLE conversa ENABLE ROW LEVEL SECURITY;")

    # Enable RLS on mensagem (chat messages - cascades through conversa)
    op.execute("ALTER TABLE mensagem ENABLE ROW LEVEL SECURITY;")

    # Enable RLS on cliente_final (end customers)
    op.execute("ALTER TABLE cliente_final ENABLE ROW LEVEL SECURITY;")

    # Enable RLS on fonte_de_dados (data sources)
    op.execute("ALTER TABLE fonte_de_dados ENABLE ROW LEVEL SECURITY;")

    # Enable RLS on credencial_servico_externo (external service credentials)
    op.execute("ALTER TABLE credencial_servico_externo ENABLE ROW LEVEL SECURITY;")

    # =========================================================================
    # 3. CREATE RLS POLICIES
    # =========================================================================

    # Policy: cliente_vizu - clients can only see their own record
    # Uses app.current_cliente_id set by the application
    op.execute("""
    CREATE POLICY cliente_vizu_isolation ON cliente_vizu
        FOR ALL
        USING (id = COALESCE(
            current_setting('app.current_cliente_id', true)::uuid,
            '00000000-0000-0000-0000-000000000000'::uuid
        ));
    """)

    # Policy: conversa - clients can only see their own conversations
    op.execute("""
    CREATE POLICY conversa_isolation ON conversa
        FOR ALL
        USING (cliente_vizu_id = COALESCE(
            current_setting('app.current_cliente_id', true)::uuid,
            '00000000-0000-0000-0000-000000000000'::uuid
        ));
    """)

    # Policy: mensagem - clients can only see messages from their conversations
    # Uses JOIN to conversa to check ownership
    op.execute("""
    CREATE POLICY mensagem_isolation ON mensagem
        FOR ALL
        USING (
            conversa_id IN (
                SELECT id FROM conversa
                WHERE cliente_vizu_id = COALESCE(
                    current_setting('app.current_cliente_id', true)::uuid,
                    '00000000-0000-0000-0000-000000000000'::uuid
                )
            )
        );
    """)

    # Policy: cliente_final - clients can only see their own end customers
    op.execute("""
    CREATE POLICY cliente_final_isolation ON cliente_final
        FOR ALL
        USING (cliente_vizu_id = COALESCE(
            current_setting('app.current_cliente_id', true)::uuid,
            '00000000-0000-0000-0000-000000000000'::uuid
        ));
    """)

    # Policy: fonte_de_dados - clients can only see their own data sources
    op.execute("""
    CREATE POLICY fonte_de_dados_isolation ON fonte_de_dados
        FOR ALL
        USING (cliente_vizu_id = COALESCE(
            current_setting('app.current_cliente_id', true)::uuid,
            '00000000-0000-0000-0000-000000000000'::uuid
        ));
    """)

    # Policy: credencial_servico_externo - clients can only see their own credentials
    op.execute("""
    CREATE POLICY credencial_servico_externo_isolation ON credencial_servico_externo
        FOR ALL
        USING (cliente_vizu_id = COALESCE(
            current_setting('app.current_cliente_id', true)::uuid,
            '00000000-0000-0000-0000-000000000000'::uuid
        ));
    """)

    # =========================================================================
    # 4. CREATE SERVICE ROLE (bypasses RLS for admin operations)
    # =========================================================================

    # Create a service role that bypasses RLS (for admin/migration operations)
    op.execute("""
    DO $$
    BEGIN
        -- Grant bypass to postgres (superuser) automatically has it
        -- For service accounts, they need to SET ROLE or use service_role

        -- Create policy for service role to bypass RLS
        -- This is automatically granted to superusers in Supabase

        -- Force RLS for all users except superusers
        ALTER TABLE cliente_vizu FORCE ROW LEVEL SECURITY;
        ALTER TABLE conversa FORCE ROW LEVEL SECURITY;
        ALTER TABLE mensagem FORCE ROW LEVEL SECURITY;
        ALTER TABLE cliente_final FORCE ROW LEVEL SECURITY;
        ALTER TABLE fonte_de_dados FORCE ROW LEVEL SECURITY;
        ALTER TABLE credencial_servico_externo FORCE ROW LEVEL SECURITY;
    END
    $$;
    """)

    # =========================================================================
    # 5. CREATE HELPER FUNCTION TO SET CURRENT CLIENT
    # =========================================================================

    op.execute("""
    CREATE OR REPLACE FUNCTION set_current_cliente_id(cliente_id UUID)
    RETURNS VOID AS $$
    BEGIN
        PERFORM set_config('app.current_cliente_id', cliente_id::text, false);
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)

    # Grant execute to authenticated users (Supabase pattern)
    op.execute("""
    GRANT EXECUTE ON FUNCTION set_current_cliente_id(UUID) TO PUBLIC;
    """)


def downgrade() -> None:
    # Drop helper function
    op.execute("DROP FUNCTION IF EXISTS set_current_cliente_id(UUID);")

    # Disable FORCE RLS
    op.execute("ALTER TABLE cliente_vizu NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE conversa NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE mensagem NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE cliente_final NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE fonte_de_dados NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE credencial_servico_externo NO FORCE ROW LEVEL SECURITY;")

    # Drop policies
    op.execute("DROP POLICY IF EXISTS cliente_vizu_isolation ON cliente_vizu;")
    op.execute("DROP POLICY IF EXISTS conversa_isolation ON conversa;")
    op.execute("DROP POLICY IF EXISTS mensagem_isolation ON mensagem;")
    op.execute("DROP POLICY IF EXISTS cliente_final_isolation ON cliente_final;")
    op.execute("DROP POLICY IF EXISTS fonte_de_dados_isolation ON fonte_de_dados;")
    op.execute(
        "DROP POLICY IF EXISTS credencial_servico_externo_isolation ON credencial_servico_externo;"
    )

    # Disable RLS
    op.execute("ALTER TABLE cliente_vizu DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE conversa DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE mensagem DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE cliente_final DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE fonte_de_dados DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE credencial_servico_externo DISABLE ROW LEVEL SECURITY;")

    # Drop column and index
    op.execute("DROP INDEX IF EXISTS ix_conversa_cliente_vizu_id;")
    op.execute("ALTER TABLE conversa DROP COLUMN IF EXISTS cliente_vizu_id;")
