# Vizu Mono

Monorepo para a plataforma Vizu - Assistentes de IA conversacionais para negócios.

## 🏗️ Arquitetura

```
vizu-mono/
├── services/           # Microserviços (FastAPI + uvicorn)
│   ├── atendente_core/     # Orquestrador de IA conversacional (LangGraph)
│   ├── tool_pool_api/      # Pool de ferramentas MCP (RAG, SQL)
│   ├── embedding_service/  # Serviço de embeddings
│   └── ...
├── libs/               # Bibliotecas compartilhadas
│   ├── vizu_llm_service/   # Cliente LLM multi-provider
│   ├── vizu_rag_factory/   # Factory de ferramentas RAG
│   ├── vizu_db_connector/  # Conexão e migrations PostgreSQL
│   └── ...
├── ferramentas/        # Ferramentas de desenvolvimento e testes
│   ├── seeds/              # Dados de desenvolvimento (clientes, RAG)
│   ├── debug.py            # Scripts de debug
│   ├── test_personas_batch.py  # Testes de personas
│   └── ...
├── docker-compose.yml  # Orquestração local
└── Makefile            # Comandos de desenvolvimento
```

## 🚀 Quick Start

```bash
# 1. Clonar e configurar ambiente
cp .env.example .env  # Editar com suas chaves

# 2. Subir todos os serviços
make up

# 3. Verificar status
make ps

# 4. Testar o chat
make chat

# 5. Rodar batch de testes (gera traces no Langfuse)
make batch-run
```

## 📋 Comandos Principais

```bash
make help          # Ver todos os comandos disponíveis
make up            # Subir serviços
make down          # Parar serviços
make logs s=<svc>  # Ver logs de um serviço
make chat          # Teste rápido do endpoint /chat
make batch-run     # Batch de 10 mensagens (gera traces Langfuse)
make migrate       # Aplicar migrations (local)
make seed          # Popular banco com dados de desenvolvimento
```

## 🔧 Configuração de LLM

O sistema suporta múltiplos providers de LLM via `vizu_llm_service`:

| Provider | Uso | Configuração |
|----------|-----|--------------|
| `ollama` | Local (container) | `OLLAMA_BASE_URL` |
| `ollama_cloud` | Ollama Cloud API | `OLLAMA_CLOUD_API_KEY` |
| `openai` | OpenAI API | `OPENAI_API_KEY` |
| `anthropic` | Claude API | `ANTHROPIC_API_KEY` |

Definir o provider no `.env`:
```bash
LLM_PROVIDER=ollama_cloud
OLLAMA_CLOUD_API_KEY=sua-chave-aqui
```

## 📊 Observabilidade

- **Langfuse**: Traces de LLM e RAG
- **OpenTelemetry**: Métricas e spans

```bash
# Local Langfuse
make langfuse-up     # Subir Langfuse local (http://localhost:3000)
make langfuse-check  # Verificar conexão

# Ver traces
make batch-run       # Gera traces para visualizar no Langfuse
```

## 🛠️ Desenvolvimento

```bash
make fmt       # Formatar código (ruff)
make lint      # Verificar lint
make test      # Rodar testes (atendente_core)
make shell     # Acessar container
```

## 📚 Documentação

### Text-to-SQL (Phase 0 & 1)
- **[Phase 0 Completion](docs/PHASE_0_COMPLETION_REPORT.md)** - Core infrastructure (schema introspection, RLS audit, SQL validation)
- **[Phase 1 Summary](docs/PHASE_1_COMPLETION_SUMMARY.md)** - Prompt template, builder, LLM config, validator
- **[Phase 1→2 Integration](docs/PHASE_1_TO_PHASE_2_INTEGRATION.md)** - Preparation for Phase 2 execution
- **[Phase 1 Deliverables](docs/PHASE_1_DELIVERABLES_MANIFEST.md)** - Complete inventory of all Phase 1 files

### Other Documentation
- [Troubleshooting](docs/troubleshooting_session_2024_12_02.md)
- [Migrations](MIGRATIONS.md)
- [FastMCP](Fast_MCP.md)

### Phase 1 Components

**Location**: `libs/vizu_prompt_management/`, `libs/vizu_llm_service/`, `libs/vizu_sql_factory/`

```python
# Import Phase 1 components
from vizu_prompt_management import TextToSqlPromptBuilder, get_prompt_builder
from vizu_llm_service import TextToSqlLLMConfig, TextToSqlLLMCall, get_llm_call
from vizu_sql_factory import ExemplarValidator, get_validator

# Usage (Phase 2: will integrate into sql_tool)
builder = get_prompt_builder()
prompt = await builder.build_from_parts(
    question="How many customers?",
    tenant_id="tenant-123",
    role="analyst"
)

llm_call = get_llm_call()
response = await llm_call.invoke(prompt)
```
