# =============================================================================
# Makefile for Vizu Mono - Development Environment
# =============================================================================
#
# Uso: make <target>
#
# Este Makefile centraliza todos os comandos de desenvolvimento do monorepo.
# Usa o .env da raiz como fonte única de configuração.
#
# =============================================================================

COMPOSE = docker compose
SHELL := /bin/bash

# Auto-load .env
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Defaults
SERVICE ?= atendente_core

.PHONY: help
.DEFAULT_GOAL := help

# =============================================================================
# HELP
# =============================================================================

help:
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════╗"
	@echo "║               🚀 Vizu Mono - Development Commands                  ║"
	@echo "╚═══════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📦 DOCKER COMPOSE"
	@echo "   make up              Build and start all services"
	@echo "   make down            Stop and remove containers"
	@echo "   make restart         Restart SERVICE=<name> (default: atendente_core)"
	@echo "   make logs            Tail logs (all services)"
	@echo "   make logs s=<name>   Tail logs for specific service"
	@echo "   make ps              Show running containers"
	@echo "   make build           Rebuild all images (no cache)"
	@echo "   make build-s         Rebuild SERVICE=<name> only"
	@echo ""
	@echo "☁️  CLOUD RUN DEPLOYMENT"
	@echo "   make setup-gcp       Install gcloud CLI (team setup)"
	@echo "   make compose-cloud   Start 3-group architecture (local test)"
	@echo "   make compose-cloud-down  Stop 3-group architecture"
	@echo "   make image-list      List published images in Artifact Registry"
	@echo ""
	@echo "🗄️  DATABASE & MIGRATIONS"
	@echo "   make migrate         Apply migrations (local Docker)"
	@echo "   make migrate-prod    Apply migrations (Supabase - with confirmation)"
	@echo "   make migrate-status  Show current migration version"
	@echo "   make db-shell        Open psql shell"
	@echo ""
	@echo "🌱 SEEDS (Dados de Desenvolvimento)"
	@echo "   make seed            Run all seeds (DB + Qdrant)"
	@echo "   make seed-db         Seed only database (clients)"
	@echo "   make seed-qdrant     Seed only Qdrant (RAG knowledge)"
	@echo "   make seed-check      Verify current seed state"
	@echo ""
	@echo "🧪 TESTING"
	@echo "   make test            Run unit tests (atendente_core)"
	@echo "   make test-s          Run tests for SERVICE=<name>"
	@echo "   make test-all        Run tests for all services"
	@echo "   make chat            Quick chat test via curl"
	@echo "   make test-vendas     Test vendas_agent endpoint"
	@echo "   make test-support    Test support_agent endpoint"
	@echo "   make test-agents     Test all agent endpoints"
	@echo "   make smoke-test      Comprehensive E2E smoke test"
	@echo "   make test-personas   Persona RAG tests (verbose)"
	@echo "   make test-personas-quick  Persona RAG tests (summary)"
	@echo "   make batch-run       Run batch test (10 messages, generates Langfuse traces)"
	@echo ""
	@echo "🧪 EXPERIMENTS & EVALUATION"
	@echo "   make experiment-run     Run experiment (MANIFEST=path/to/manifest.yaml)"
	@echo "   make experiment-workflow Run LangGraph workflow experiment (MANIFEST=path/to/manifest.yaml)"
	@echo "   make experiment-workflow-v2-export  Run with CSV export"
	@echo "   make experiment-classify Classify experiment results (RUN_ID=uuid)"
	@echo "   make experiment-export  Export experiment data (RUN_ID=uuid)"
	@echo "   make experiment-sync    Sync manifest to Langfuse (MANIFEST=path/to/manifest.yaml)"
	@echo "   make experiment-ui      Launch evaluation suite Streamlit UI"
	@echo ""
	@echo "📊 DATA LOADERS"
	@echo "   make data-load-whatsapp Load WhatsApp chat (INPUT=file.txt OUTPUT=out.csv)"
	@echo "   make data-anonymize     Anonymize CSV with Presidio (INPUT=raw.csv OUTPUT=clean.csv)"
	@echo ""
	@echo "🔧 DEVELOPMENT"
	@echo "   make shell           Shell into SERVICE=<name> container"
	@echo "   make fmt             Format code (ruff) - services + libs"
	@echo "   make lint            Lint code (ruff check) - services + libs"
	@echo "   make lint-fix        Auto-fix lint issues (unused imports)"
	@echo "   make clean           Prune Docker cache"
	@echo ""
	@echo "📊 OBSERVABILITY"
	@echo "   make langfuse-check  Verify Langfuse connection"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Environment:"
	@echo "   SUPABASE_URL:    $(if $(SUPABASE_URL),✅ SET,❌ NOT SET)"
	@echo "   LANGFUSE_HOST:   $(if $(LANGFUSE_HOST),✅ $(LANGFUSE_HOST),❌ NOT SET)"
	@echo "   EMBEDDING_MODEL: $(if $(EMBEDDING_MODEL_NAME),$(EMBEDDING_MODEL_NAME),intfloat/multilingual-e5-large)"
	@echo ""

# =============================================================================
# DOCKER COMPOSE
# =============================================================================

.PHONY: up down restart logs ps build build-s compose-cloud compose-cloud-down

up:
	@echo "🚀 Starting all services..."
	$(COMPOSE) up --build -d
	@echo "✅ Services started. Use 'make logs' to tail logs."

down:
	@echo "🛑 Stopping services..."
	$(COMPOSE) down

restart:
	@echo "🔄 Restarting $(SERVICE)..."
	$(COMPOSE) restart $(SERVICE)
	@echo "✅ $(SERVICE) restarted"

logs:
ifdef s
	$(COMPOSE) logs -f --tail=100 $(s)
else
	$(COMPOSE) logs -f --tail=100
endif

ps:
	$(COMPOSE) ps

build:
	@echo "🔨 Building all images (no cache)..."
	$(COMPOSE) build --no-cache

build-s:
	@echo "🔨 Building $(SERVICE)..."
	$(COMPOSE) build --no-cache $(SERVICE)
	$(COMPOSE) up -d $(SERVICE)
	@echo "✅ $(SERVICE) rebuilt and started"

# =============================================================================
# CLOUD RUN - LOCAL 3-GROUP ARCHITECTURE
# =============================================================================

compose-cloud:
	@echo "🚀 Starting 3-group Cloud Run architecture (local)..."
	@echo "   GROUP 1: agents-pool (ports 8003-8006)"
	@echo "   GROUP 2: workers-pool (ports 8007-8009)"
	@echo "   GROUP 3: embedding-service (port 11435)"
	$(COMPOSE) -f docker-compose.cloud-run.yml up --build -d
	@echo "✅ Cloud Run architecture running"
	@echo "📝 Test endpoints: curl http://localhost:8003/health"

compose-cloud-down:
	@echo "🛑 Stopping Cloud Run architecture..."
	$(COMPOSE) -f docker-compose.cloud-run.yml down
	@echo "✅ Stopped"

# =============================================================================
# DATABASE & MIGRATIONS
# =============================================================================

.PHONY: migrate migrate-prod migrate-status db-shell

migrate:
	@echo "🔄 Running migrations (local Docker)..."
	@docker exec vizu_atendente_core python -c "\
import sys; \
sys.path.insert(0, '/app/libs/vizu_db_connector/src'); \
sys.path.insert(0, '/app/libs/vizu_models/src'); \
from alembic.config import Config; \
from alembic import command; \
import os; \
cfg = Config('/app/libs/vizu_db_connector/alembic.ini'); \
cfg.set_main_option('sqlalchemy.url', os.environ['DATABASE_URL']); \
cfg.set_main_option('script_location', '/app/libs/vizu_db_connector/alembic'); \
command.upgrade(cfg, 'head'); \
print('✅ Migrations applied!')"

migrate-prod:
	@if [ -z "$(SUPABASE_DB_URL)" ]; then \
		echo "❌ SUPABASE_DB_URL not set in .env"; \
		exit 1; \
	fi
	@echo "⚠️  This will modify PRODUCTION database!"
	@echo "   URL: $$(echo '$(SUPABASE_DB_URL)' | sed 's/:.*@/:***@/')"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@cd libs/vizu_db_connector && \
		DATABASE_URL="$(SUPABASE_DB_URL)" \
		PYTHONPATH="$(PWD)/libs/vizu_models/src:$(PWD)/libs/vizu_db_connector/src" \
		poetry run alembic upgrade head
	@echo "✅ Migrations applied to Supabase!"

migrate-status:
	@echo "📊 Migration status..."
	@docker exec vizu_atendente_core python -c "\
from sqlalchemy import create_engine, text; \
import os; \
engine = create_engine(os.environ['DATABASE_URL']); \
conn = engine.connect(); \
result = conn.execute(text('SELECT version_num FROM alembic_version')); \
row = result.fetchone(); \
print('Current version:', row[0] if row else 'No migrations'); \
conn.close()"

db-shell:
	$(COMPOSE) exec -it postgres psql -U user -d vizu_db

# =============================================================================
# SEEDS
# =============================================================================

.PHONY: seed seed-db seed-qdrant seed-check

seed: seed-db seed-qdrant
	@echo "✅ All seeds completed!"

seed-db:
	@echo "🌱 Seeding database..."
	@docker exec -e PYTHONPATH=/app:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src:/app \
		vizu_atendente_core python -m ferramentas.seeds.run_seeds --db

seed-qdrant:
	@echo "🌱 Seeding Qdrant..."
	@docker exec \
		-e PYTHONPATH=/app:/app/libs/vizu_qdrant_client/src:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-e QDRANT_URL=http://qdrant_db:6333 \
		-e EMBEDDING_SERVICE_URL=http://embedding_service:11435 \
		vizu_atendente_core python -m ferramentas.seeds.run_seeds --qdrant

seed-check:
	@echo "📊 Checking seed state..."
	@docker exec \
		-e PYTHONPATH=/app:/app/libs/vizu_qdrant_client/src:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-e QDRANT_URL=http://qdrant_db:6333 \
		vizu_atendente_core python -m ferramentas.seeds.run_seeds --check

# =============================================================================
# TESTING
# =============================================================================

.PHONY: test test-s test-all chat batch-run test-vendas test-support test-agents smoke-test

test:
	@echo "🧪 Running tests for atendente_core..."
	cd services/atendente_core && poetry run pytest tests/ -v --tb=short

test-s:
	@echo "🧪 Running tests for $(SERVICE)..."
	cd services/$(SERVICE) && poetry run pytest tests/ -v --tb=short

test-all:
	@echo "🧪 Running all tests..."
	@for svc in atendente_core tool_pool_api vendas_agent support_agent; do \
		echo "Testing $$svc..."; \
		cd services/$$svc && poetry run pytest tests/ -v --tb=short 2>/dev/null || true; \
		cd ../..; \
	done

test-vendas:
	@echo "💰 Testing vendas_agent..."
	@API_KEY=$$(docker exec vizu_atendente_core python /app/scripts/get_api_key.py 2>/dev/null) && \
	curl -s -X POST "http://localhost:8009/chat" \
		-H "Content-Type: application/json" \
		-H "X-API-KEY: $$API_KEY" \
		-d '{"message": "Quero comprar um produto", "session_id": "test-vendas-'$$(date +%s)'"}' | python3 -m json.tool 2>/dev/null || echo "❌ Request failed"

test-support:
	@echo "🛠️ Testing support_agent..."
	@API_KEY=$$(docker exec vizu_atendente_core python /app/scripts/get_api_key.py 2>/dev/null) && \
	curl -s -X POST "http://localhost:8010/chat" \
		-H "Content-Type: application/json" \
		-H "X-API-KEY: $$API_KEY" \
		-d '{"message": "Tenho um problema técnico", "session_id": "test-support-'$$(date +%s)'"}' | python3 -m json.tool 2>/dev/null || echo "❌ Request failed"

test-agents:
	@echo "🤖 Testing all agents..."
	@make chat
	@echo ""
	@make test-vendas
	@echo ""
	@make test-support

smoke-test:
	@echo "🔥 Running comprehensive smoke test..."
	@echo ""
	@echo "1️⃣ Checking services status..."
	@$(COMPOSE) ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(atendente|vendas|support|tool_pool)"
	@echo ""
	@echo "2️⃣ Testing tool_pool_api MCP..."
	@curl -s http://localhost:8006/health 2>/dev/null && echo "✅ tool_pool_api healthy" || echo "❌ tool_pool_api unhealthy"
	@echo ""
	@echo "3️⃣ Testing atendente_core with RAG tool..."
	@API_KEY=$$(docker exec vizu_atendente_core python /app/scripts/get_api_key.py 2>/dev/null) && \
	echo "Testing RAG query..." && \
	curl -s -X POST "http://localhost:8003/chat" \
		-H "Content-Type: application/json" \
		-H "X-API-KEY: $$API_KEY" \
		-d '{"message": "Busque informações sobre os produtos disponíveis", "session_id": "smoke-rag-'$$(date +%s)'"}' | python3 -m json.tool 2>/dev/null | head -20 || echo "❌ RAG test failed"
	@echo ""
	@echo "4️⃣ Testing vendas_agent..."
	@API_KEY=$$(docker exec vizu_atendente_core python /app/scripts/get_api_key.py 2>/dev/null) && \
	curl -s -X POST "http://localhost:8009/chat" \
		-H "Content-Type: application/json" \
		-H "X-API-KEY: $$API_KEY" \
		-d '{"message": "Qual o preço do produto X?", "session_id": "smoke-vendas-'$$(date +%s)'"}' 2>/dev/null | head -c 500 && echo "..." || echo "❌ vendas_agent test failed"
	@echo ""
	@echo "5️⃣ Testing support_agent..."
	@API_KEY=$$(docker exec vizu_atendente_core python /app/scripts/get_api_key.py 2>/dev/null) && \
	curl -s -X POST "http://localhost:8010/chat" \
		-H "Content-Type: application/json" \
		-H "X-API-KEY: $$API_KEY" \
		-d '{"message": "Meu sistema não está funcionando", "session_id": "smoke-support-'$$(date +%s)'"}' 2>/dev/null | head -c 500 && echo "..." || echo "❌ support_agent test failed"
	@echo ""
	@echo "✅ Smoke test complete!"

test-personas:
	@echo "🧪 Running persona-based RAG tests..."
	@cd ferramentas && poetry run python persona_rag_tests.py -v

test-personas-quick:
	@echo "🧪 Running persona-based RAG tests (summary only)..."
	@cd ferramentas && poetry run python persona_rag_tests.py

batch-run:
	@echo "🚀 Running batch test (generates Langfuse traces)..."
	@docker exec -e PYTHONPATH=/app \
		vizu_atendente_core python /app/scripts/batch_run.py

chat:
	@echo "💬 Testing chat endpoint..."
	@API_KEY=$$(docker exec vizu_atendente_core python /app/scripts/get_api_key.py 2>/dev/null) && \
	if [ -z "$$API_KEY" ]; then \
		echo "❌ No client found. Run 'make seed' first."; \
		exit 1; \
	fi && \
	echo "Using API Key: $${API_KEY:0:8}..." && \
	curl -s -X POST "http://localhost:8003/chat" \
		-H "Content-Type: application/json" \
		-H "X-API-KEY: $$API_KEY" \
		-d '{"message": "Olá, quais são os serviços disponíveis?", "session_id": "test-'$$(date +%s)'"}' | python3 -m json.tool 2>/dev/null || echo "❌ Request failed"

# =============================================================================
# EXPERIMENTS & EVALUATION
# =============================================================================

.PHONY: experiment-run experiment-classify experiment-export experiment-sync experiment-ui experiment-workflow

experiment-run:
	@echo "🧪 Running experiment..."
	@if [ -z "$(MANIFEST)" ]; then \
		echo "❌ Please specify MANIFEST=path/to/manifest.yaml"; \
		echo "   Example: make experiment-run MANIFEST=ferramentas/evaluation_suite/workflows/atendente/example_manifest.yaml"; \
		exit 1; \
	fi && \
	docker exec -e PYTHONPATH=/app:/app/libs/vizu_experiment_service/src:/app/libs/vizu_models/src:/app/libs/vizu_db_connector/src \
		vizu_atendente_core python -m vizu_experiment_service.cli run "$(MANIFEST)" --legacy --created-by "$$(whoami)"

experiment-workflow:
	@echo "🔄 Running LangGraph workflow experiment..."
	@if [ -z "$(MANIFEST)" ]; then \
		echo "❌ Please specify MANIFEST=path/to/manifest.yaml"; \
		echo "   Example: make experiment-workflow MANIFEST=ferramentas/evaluation_suite/workflows/boleta_trader/manifest.yaml"; \
		exit 1; \
	fi && \
	docker exec -e PYTHONPATH=/app:/app/libs/vizu_experiment_service/src:/app/libs/vizu_models/src:/app/libs/vizu_db_connector/src:/app/ferramentas/evaluation_suite/workflows \
		-w /app \
		vizu_atendente_core python -m vizu_experiment_service.cli workflow "$(MANIFEST)" --created-by "$$(whoami)"

# Run workflow experiment with JSON output (default - always saves results file)
experiment-workflow-local:
	@echo "🔬 Running workflow experiment..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest.yaml

# Run workflow experiment with database storage
experiment-workflow-db:
	@echo "🔬 Running workflow experiment with DB storage..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest.yaml --db

# Run workflow experiment with Langfuse tracing
experiment-workflow-langfuse:
	@echo "🔬 Running workflow experiment with Langfuse tracing..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest.yaml --langfuse

# Run workflow experiment with both DB and Langfuse
experiment-workflow-full:
	@echo "🔬 Running workflow experiment with DB + Langfuse..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest.yaml --db --langfuse

# ============================================================================
# V2 Workflow Experiments (vizu_llm_service - multi-provider support)
# ============================================================================

# Run workflow v2 with local Ollama (default)
experiment-workflow-v2:
	@echo "🔬 Running workflow v2 (vizu_llm_service)..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_llm_service/src:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest_v2.yaml

# Run workflow v2 with Ollama Cloud
experiment-workflow-v2-cloud:
	@echo "🔬 Running workflow v2 with Ollama Cloud..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_llm_service/src:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-e LLM_PROVIDER=ollama_cloud \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest_v2.yaml

# Run workflow v2 with MCP tools enabled
experiment-workflow-v2-mcp:
	@echo "🔬 Running workflow v2 with MCP tools..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_llm_service/src:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-e ENABLE_MCP_TOOLS=true \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest_v2.yaml

# Run workflow v2 with full options (Langfuse + DB + custom provider)
# Usage: make experiment-workflow-v2-full LLM_PROVIDER=openai
experiment-workflow-v2-full:
	@echo "🔬 Running workflow v2 with full options..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_llm_service/src:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-e LLM_PROVIDER=$(or $(LLM_PROVIDER),ollama) \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest_v2.yaml --db --langfuse

# Export results to CSV with query and node outputs
experiment-workflow-v2-export:
	@echo "🔬 Running workflow v2 with CSV export..."
	@docker exec -e PYTHONPATH=/app:/app/ferramentas:/app/libs/vizu_llm_service/src:/app/libs/vizu_db_connector/src:/app/libs/vizu_models/src \
		-e LLM_PROVIDER=$(or $(LLM_PROVIDER),ollama_cloud) \
		-w /app \
		vizu_atendente_core python -m ferramentas.evaluation_suite.workflows.boleta_trader.run_experiment \
		ferramentas/evaluation_suite/workflows/boleta_trader/manifest_v2.yaml --export-csv

experiment-classify:
	@echo "📊 Classifying experiment results..."
	@if [ -z "$(RUN_ID)" ]; then \
		echo "❌ Please specify RUN_ID=experiment-run-id"; \
		echo "   Example: make experiment-classify RUN_ID=12345678-1234-1234-1234-123456789012"; \
		exit 1; \
	fi && \
	docker exec -e PYTHONPATH=/app:/app/libs/vizu_experiment_service/src:/app/libs/vizu_models/src:/app/libs/vizu_db_connector/src \
		vizu_atendente_core python -m vizu_experiment_service.cli classify "$(RUN_ID)"

experiment-export:
	@echo "📤 Exporting experiment data..."
	@if [ -z "$(RUN_ID)" ]; then \
		echo "❌ Please specify RUN_ID=experiment-run-id"; \
		echo "   Example: make experiment-export RUN_ID=12345678-1234-1234-1234-123456789012"; \
		exit 1; \
	fi && \
	docker exec -e PYTHONPATH=/app:/app/libs/vizu_experiment_service/src:/app/libs/vizu_models/src:/app/libs/vizu_db_connector/src \
		vizu_atendente_core python -m vizu_experiment_service.cli export "$(RUN_ID)" --format jsonl

experiment-sync:
	@echo "🔄 Syncing manifest to Langfuse..."
	@if [ -z "$(MANIFEST)" ]; then \
		echo "❌ Please specify MANIFEST=path/to/manifest.yaml"; \
		echo "   Example: make experiment-sync MANIFEST=ferramentas/evaluation_suite/workflows/atendente/example_manifest.yaml"; \
		exit 1; \
	fi && \
	docker exec -e PYTHONPATH=/app:/app/libs/vizu_experiment_service/src:/app/libs/vizu_models/src:/app/libs/vizu_db_connector/src \
		vizu_atendente_core python -m vizu_experiment_service.cli sync "$(MANIFEST)"

experiment-ui:
	@echo "🎨 Launching evaluation suite UI..."
	@echo "📱 Opening Streamlit app at http://localhost:8501"
	@docker compose up -d evaluation_suite

# =============================================================================
# DATA LOADERS
# =============================================================================

.PHONY: data-load-whatsapp data-anonymize

# Load WhatsApp chat export to CSV (with anonymization)
# Usage: make data-load-whatsapp INPUT=path/to/chat.txt OUTPUT=path/to/output.csv
data-load-whatsapp:
	@echo "📱 Loading WhatsApp chat export..."
	@if [ -z "$(INPUT)" ]; then \
		echo "❌ Please specify INPUT=path/to/chat.txt"; \
		echo "   Example: make data-load-whatsapp INPUT=ferramentas/evaluation_suite/workflows/boleta_trader/data/raw/chat.txt"; \
		exit 1; \
	fi && \
	docker exec -e PYTHONPATH=/app:/app/ferramentas/evaluation_suite/src \
		-w /app \
		vizu_atendente_core python -m evaluation_suite.data_loaders.whatsapp_loader \
		"$(INPUT)" -o "$(or $(OUTPUT),ferramentas/evaluation_suite/workflows/boleta_trader/data/processed/whatsapp_anonymized.csv)" \
		--add-test-id

# Anonymize existing CSV (for CSVs not from WhatsApp)
# Usage: make data-anonymize INPUT=path/to/raw.csv OUTPUT=path/to/anonymized.csv
data-anonymize:
	@echo "🔒 Anonymizing CSV..."
	@if [ -z "$(INPUT)" ]; then \
		echo "❌ Please specify INPUT=path/to/raw.csv"; \
		echo "   Example: make data-anonymize INPUT=ferramentas/evaluation_suite/workflows/boleta_trader/data/raw/data.csv"; \
		exit 1; \
	fi && \
	docker exec -e PYTHONPATH=/app:/app/ferramentas/evaluation_suite/src \
		-w /app \
		vizu_atendente_core python -m evaluation_suite.data_loaders.pii_anonymizer \
		"$(INPUT)" -o "$(or $(OUTPUT),ferramentas/evaluation_suite/workflows/boleta_trader/data/processed/anonymized.csv)" \
		--add-test-id

# Create a small anonymized WhatsApp sample (first 25%) and anonymize it with Presidio
# Usage: make data-whats-amostra INPUT=path/to/processed/whatsapp.csv SAMPLE_OUT=path/to/sample.csv OUTPUT=path/to/anonymized.csv
.PHONY: data-whats-amostra
data-whats-amostra:
	@echo "📱 Creating first-quarter WhatsApp sample and anonymizing with Presidio..."
	@if [ -z "$(INPUT)" ]; then \
		echo "❌ Please specify INPUT=path/to/processed/whatsapp_test.csv"; \
		echo "   Example: make data-whats-amostra INPUT=ferramentas/evaluation_suite/workflows/boleta_trader/data/processed/whatsapp_test.csv"; \
		exit 1; \
	fi && \
	SAMPLE="$(or $(SAMPLE_OUT),ferramentas/evaluation_suite/workflows/boleta_trader/data/raw/whats_amostra.csv)"; \
	OUT="$(or $(OUTPUT),ferramentas/evaluation_suite/workflows/boleta_trader/data/processed/whats_amostra_anonymized.csv)"; \
	# Slice the first 25% of INPUT to SAMPLE
	docker exec -e PYTHONPATH=/app:/app/ferramentas/evaluation_suite/src \
		-w /app \
		vizu_atendente_core python -c "import pandas as pd; df = pd.read_csv('$(INPUT)'); q = max(1, len(df)//4); df.iloc[:q].to_csv('$$SAMPLE', index=False); print('Saved sample to', '$$SAMPLE')" || exit 1; \
	# Run Presidio anonymizer on the sample
	docker exec -e PYTHONPATH=/app:/app/ferramentas/evaluation_suite/src \
		-w /app \
		vizu_atendente_core python -m evaluation_suite.data_loaders.pii_anonymizer "$$SAMPLE" -o "$$OUT" --add-test-id || exit 1; \
	@echo "✅ Anonymized sample saved to $$OUT"

# =============================================================================
# DEVELOPMENT
# =============================================================================

.PHONY: shell fmt lint clean

shell:
	$(COMPOSE) exec $(SERVICE) bash

fmt:
	@echo "🎨 Formatting code..."
	@for dir in services/*/ libs/*/; do \
		if [ -f "$$dir/pyproject.toml" ]; then \
			echo "  Formatting $$dir..."; \
			(cd "$$dir" && poetry run ruff format . 2>/dev/null) || true; \
		fi \
	done
	@echo "✅ Done"

lint:
	@echo "🔍 Linting code..."
	@for dir in services/*/ libs/*/; do \
		if [ -f "$$dir/pyproject.toml" ]; then \
			echo "  Linting $$dir..."; \
			(cd "$$dir" && poetry run ruff check . 2>/dev/null) || true; \
		fi \
	done

lint-fix:
	@echo "🔧 Fixing lint issues (unused imports, etc)..."
	@for dir in services/*/ libs/*/; do \
		if [ -f "$$dir/pyproject.toml" ]; then \
			echo "  Fixing $$dir..."; \
			(cd "$$dir" && poetry run ruff check --fix --select F401,F841 . 2>/dev/null) || true; \
		fi \
	done
	@echo "✅ Done"

clean:
	@echo "🧹 Cleaning Docker cache..."
	docker builder prune -f
	docker image prune -f
	@echo "✅ Cleaned"

# =============================================================================
# OBSERVABILITY
# =============================================================================

.PHONY: langfuse-check langfuse-up langfuse-down langfuse-logs setup-gcp image-list

setup-gcp:
	@echo "⚙️  Installing gcloud CLI for team..."
	@chmod +x scripts/setup-gcp-cli.sh
	@./scripts/setup-gcp-cli.sh

image-list:
	@if [ -z "$$GCP_PROJECT_ID" ]; then \
		echo "❌ GCP_PROJECT_ID not set in .env"; \
		echo "Run: gcloud config set project YOUR_PROJECT_ID"; \
		exit 1; \
	fi
	@echo "📦 Images in Artifact Registry (us-east1-docker.pkg.dev/$$GCP_PROJECT_ID/vizu)..."
	@gcloud artifacts docker images list us-east1-docker.pkg.dev/$$GCP_PROJECT_ID/vizu || true
	@echo ""
	@echo "💡 Tip: Set GCP_PROJECT_ID in .env to avoid the prompt above"

langfuse-check:
	@echo "🔍 Checking Langfuse connection..."
	@docker exec vizu_atendente_core python /app/scripts/check_langfuse.py

langfuse-up:
	@echo "🚀 Starting local Langfuse..."
	@cd langfuse && docker compose up -d
	@echo "✅ Langfuse running at http://localhost:3000"
	@echo "📝 First time? Create account and project, then update .env with API keys"

langfuse-down:
	@echo "⏹️  Stopping local Langfuse..."
	@cd langfuse && docker compose down

langfuse-logs:
	@cd langfuse && docker compose logs -f --tail 50
