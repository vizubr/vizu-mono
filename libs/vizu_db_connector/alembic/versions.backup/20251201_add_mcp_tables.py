"""add_prompt_template_and_knowledge_base_config tables
Revision ID: 20251201_add_mcp_tables
Revises: 20251130_add_rls_security
Create Date: 2025-12-01

Add tables for MCP Resources and Prompts support:
- prompt_template: Versioned prompts (global and per-client)
- knowledge_base_config: Knowledge base configurations per client
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251201_add_mcp_tables"
down_revision = "20251130_add_rls_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # Table: prompt_template
    # Stores versioned prompts that can be global or per-client
    # ============================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS prompt_template (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        
        -- Prompt identification
        name VARCHAR(100) NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        
        -- Content
        content TEXT NOT NULL,
        description TEXT,
        
        -- Configuration
        variables JSONB,
        is_active BOOLEAN NOT NULL DEFAULT true,
        tags JSONB,
        
        -- Ownership (NULL = global prompt, UUID = client-specific)
        cliente_vizu_id UUID REFERENCES cliente_vizu(id) ON DELETE CASCADE,
        
        -- Audit
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now(),
        created_by VARCHAR(100),
        
        -- Unique constraint: name + version + cliente_vizu_id
        CONSTRAINT uq_prompt_name_version_client UNIQUE (name, version, cliente_vizu_id)
    );
    """)

    # Indexes for prompt_template
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_prompt_template_name ON prompt_template(name);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_prompt_template_cliente ON prompt_template(cliente_vizu_id);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_prompt_template_active ON prompt_template(is_active) WHERE is_active = true;
    """)

    # ============================================================
    # Table: knowledge_base_config
    # Stores knowledge base configurations per client
    # ============================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_base_config (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        
        -- Ownership
        cliente_vizu_id UUID NOT NULL REFERENCES cliente_vizu(id) ON DELETE CASCADE,
        
        -- Base identification
        name VARCHAR(100) NOT NULL,
        description TEXT,
        
        -- Qdrant configuration
        collection_name VARCHAR(100) NOT NULL,
        embedding_model VARCHAR(100) NOT NULL DEFAULT 'text-embedding-3-small',
        
        -- Chunking configuration
        chunk_size INTEGER NOT NULL DEFAULT 512,
        chunk_overlap INTEGER NOT NULL DEFAULT 50,
        
        -- Status
        is_active BOOLEAN NOT NULL DEFAULT true,
        
        -- Configuration
        metadata_schema JSONB,
        search_config JSONB,
        
        -- Stats
        document_count INTEGER NOT NULL DEFAULT 0,
        last_sync_at TIMESTAMP,
        
        -- Audit
        created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now()
    );
    """)

    # Indexes for knowledge_base_config
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_kb_config_cliente ON knowledge_base_config(cliente_vizu_id);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_kb_config_collection ON knowledge_base_config(collection_name);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_kb_config_active ON knowledge_base_config(is_active) WHERE is_active = true;
    """)

    # ============================================================
    # Seed: Default global prompts
    # ============================================================
    op.execute("""
    INSERT INTO prompt_template (name, version, content, description, variables, tags, cliente_vizu_id)
    VALUES 
    (
        'atendente/system',
        1,
        'Você é um assistente virtual de {{nome_empresa}}.

Horário de funcionamento: {{horario_funcionamento}}
Serviços disponíveis: {{servicos}}

Seja educado, prestativo e conciso. Responda apenas sobre assuntos relacionados ao negócio.',
        'Prompt de sistema básico para atendentes virtuais',
        '{"nome_empresa": {"type": "string", "required": true}, "horario_funcionamento": {"type": "string"}, "servicos": {"type": "string"}}',
        '["system", "v1", "default"]',
        NULL
    ),
    (
        'atendente/system',
        2,
        'Você é o assistente virtual de {{nome_empresa}}.

## Contexto do Negócio
- Horário de funcionamento: {{horario_funcionamento}}
- Serviços/Produtos: {{servicos}}

## Diretrizes
1. Seja cordial e profissional
2. Responda de forma concisa e direta
3. Use a base de conhecimento quando disponível
4. Nunca invente informações - diga que não sabe se necessário
5. Ofereça alternativas quando não puder atender

## Ferramentas Disponíveis
{{ferramentas_disponiveis}}

Você pode usar as ferramentas acima para buscar informações e realizar ações.',
        'Prompt de sistema v2 com contexto expandido e ferramentas',
        '{"nome_empresa": {"type": "string", "required": true}, "horario_funcionamento": {"type": "string"}, "servicos": {"type": "string"}, "ferramentas_disponiveis": {"type": "string"}}',
        '["system", "v2", "enhanced"]',
        NULL
    ),
    (
        'rag/query',
        1,
        'Use o seguinte contexto para responder à pergunta do usuário.

## Contexto
{{context}}

## Pergunta
{{question}}

## Instruções
- Base sua resposta apenas no contexto fornecido
- Se a informação não estiver no contexto, diga que não encontrou
- Cite trechos relevantes quando apropriado',
        'Template para respostas RAG com contexto',
        '{"context": {"type": "string", "required": true}, "question": {"type": "string", "required": true}}',
        '["rag", "query"]',
        NULL
    ),
    (
        'atendente/confirmacao-agendamento',
        1,
        'Confirmando agendamento:

📅 Data: {{data}}
🕐 Horário: {{horario}}
💇 Serviço: {{servico}}

Está correto?',
        'Mensagem de confirmação de agendamento',
        '{"data": {"type": "string", "required": true}, "horario": {"type": "string", "required": true}, "servico": {"type": "string", "required": true}}',
        '["scheduling", "confirmation"]',
        NULL
    ),
    (
        'atendente/esclarecimento',
        1,
        'Não entendi completamente. {{pergunta}}

Opções disponíveis:
{{opcoes}}',
        'Prompt para pedir esclarecimento ao usuário',
        '{"pergunta": {"type": "string", "required": true}, "opcoes": {"type": "string", "required": true}}',
        '["disambiguation", "clarification"]',
        NULL
    )
    ON CONFLICT (name, version, cliente_vizu_id) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_base_config;")
    op.execute("DROP TABLE IF EXISTS prompt_template;")
