<!-- Short, focused guidance for AI coding agents working in the vizu-mono monorepo. -->
# Vizu monorepo — Copilot / AI agent instructions

These notes help an AI coding agent be productive quickly in this monorepo. They focus on concrete, discoverable patterns, file locations, and commands used by developers.

1) Big picture
- Monorepo layout: top-level folders split by responsibility:
  - services/ — runnable microservices (FastAPI + uvicorn, each with its own pyproject/Dockerfile).
  - libs/ — shared Python libraries kept alongside services and imported via PYTHONPATH or Poetry path dependencies.
  (all should be imported via Poetry)
  - infra/ and docker-configs/ — deployment and observability configs (OpenTelemetry collector, Docker compose).

- Typical runtime: each service is a Python app (3.11+) packed with Poetry and run with uvicorn in dev. Docker images copy a project-local .venv and set PYTHONPATH to include `/app/src` and `/app/libs`.

2) Where to look first (important files)
- Top-level: `docker-compose.yml` — canonical local dev composition and service names (postgres, redis, otel-collector, atendente_core, tool_pool_api, etc.).
- Service README examples: `services/atendente_core/README.md` — explains env vars and run/test commands.
- Dockerfile pattern: `services/atendente_core/Dockerfile` — multi-stage build, Poetry in builder, copies `.venv`, sets `PYTHONPATH`. Use this as the canonical Docker pattern for other services.
- Shared libs: `libs/` — examples: `vizu_db_connector`, `vizu_qdrant_client`, `vizu_models`. These are referenced by services via PYTHONPATH or Poetry path deps.

3) Common developer workflows & commands
- Local dev with Docker Compose (recommended): `docker compose up --build` (uses `docker-compose.yml`). Service names from the compose file are important when wiring env vars.
- Running a service locally without Docker (common for quick iteration):
  - cd into service directory (for example `services/atendente_core`)
  - `poetry install`
  - copy `.env.example` -> `.env` and fill values
  - `poetry run uvicorn src.<service_package>.main:app --reload` (see `services/atendente_core/README.md`); or use the exact module path used in the Dockerfile (`atendente_core.main:app`).
- Tests: per-service `pytest` via Poetry: `poetry run pytest` when run from the service directory.

4) Project-specific conventions and patterns
- Python version: 3.11+ across services. Use Poetry for dependency management; many Dockerfiles rely on Poetry creating `.venv` inside the project (`POETRY_VIRTUALENVS_IN_PROJECT=true`).
- PYTHONPATH usage: docker-compose and Dockerfiles set `PYTHONPATH` to include `/app/src` and `/app/libs` (or service-specific equivalents). When running locally, ensure the interpreter can import packages in `libs/` (Poetry path deps or `PYTHONPATH` env).
- Entrypoint pattern in Dockerfiles: multi-stage builder to install deps, copy `.venv` into final image, then `CMD` calls python/uvicorn with package module path. Prefer to match the same import path when running locally.
- DB & infra: `docker-compose.yml` exposes development ports (Postgres on 5433 -> container 5432, Redis 6379, OTEL endpoints). `db_manager` service is a CLI-style container used for migrations and DB tasks.

5) Integration points & external dependencies
- Key external systems referenced in envs and configs:
  - Postgres (see `docker-compose.yml`)
  - Redis (session/state store)
  - OpenTelemetry collector (OTEL)
  - Ollama service (local model host) — `services/ollama_service`
  - Third-party APIs: Twilio, LangChain/LangGraph keys referenced in service READMEs/env examples

- When changing code that affects inter-service API contracts, update corresponding client libraries in `libs/` or the service tests that assert API contracts.

6) Code patterns & places to edit
- FastAPI apps: service entrypoints live under `services/*/src` and follow a package structure. E.g., `services/atendente_core/src/atendente_core/main.py` (module import path used by Dockerfile/uvicorn).
- Shared model types: `libs/vizu_models/src` — prefer updating shared models here and bumping references where used.
- DB migrations / operations: `services/db_manager` and `libs/vizu_db_connector`.

7) Testing and CI notes
- CI workflows live under `.github/workflows/` (see repository). Per-service pytest runs are expected; use Poetry when running tests.
- If you change dependencies, update the service `pyproject.toml` and lock files (`poetry lock`) used by Dockerfile builder stage.

8) Helpful examples to reference in patches
- Use `services/atendente_core/Dockerfile` as the canonical multi-stage/Poetry/docker pattern.
- Use `docker-compose.yml` to discover service names, ports, and PYTHONPATH expectations.
- Use `services/atendente_core/README.md` for env var names and local run commands.

9) Safety & edit guidance for AI agents
- Keep changes minimal and focused per PR. Edit one service or one shared lib per branch where possible.
- When adding imports to services, ensure `libs/` packages are importable either by adding a Poetry path dependency or by ensuring PYTHONPATH includes the libs directory.
- Avoid changing Dockerfile multi-stage patterns unless you update the corresponding compose settings and README run commands.

If anything in these notes looks incomplete or you want examples for a particular service (tests, Dockerfile, or lib), tell me which service and I'll expand the doc with precise file paths and snippets.

10) Recent changes (important) - read before editing
- `Makefile`: added `batch-run` target which executes `scripts/batch_run.py` inside the `vizu_atendente_core` container. Avoid running this target on host Python (system-managed envs cause pip errors on macOS).
- `scripts/batch_run.py`: made container-aware (uses `http://localhost:8000/chat` inside container and `http://localhost:8003/chat` from host). When running via `make batch-run` the script runs inside the container and talks to the local `atendente_core` process.
- `services/atendente_core/src/atendente_core/core/nodes.py`: refactored `execute_tools_node` to (a) avoid trusting `cliente_id` from the LLM, (b) inject `cliente_id` from the server-side internal context, and (c) execute multiple tool calls in parallel via `asyncio.gather`.
- `services/tool_pool_api/src/tool_pool_api/server/tool_modules/rag_module.py`: added a `_rag_tool_wrapper` that hides `cliente_id` from the public tool schema. The tool accepts `cliente_id` internally but the LLM only sees `query`.
- READMEs: updated `README.md`, `services/atendente_core/README.md`, and `services/tool_pool_api/README.md` with quick-start, batch-run, and LLM/tooling notes.

11) Guidance for future agents working on this repo
- Before changing any tool schema, verify where `cliente_id` is created and validated (search for `InternalClientContext` / `_internal_context`). The server should be the source of truth for client identifiers — never rely on LLM-provided IDs.
- When adding or updating tools, prefer a thin wrapper that exposes only safe parameters to the LLM (e.g., `query`) and keeps authentication/context injection server-side.
- Use `asyncio` and `async` interfaces where possible for tools to enable parallel execution. If a tool is sync-only, prefer exposing an `ainvoke` wrapper or use `asyncio.to_thread` in a bounded task pool to avoid blocking the event loop.
- Langfuse traces: instrument both tool execution and the supervisor steps. Include `tool_call_id` and `session_id` in spans so traces correlate across services.
- When modifying libs under `libs/`, update their `pyproject.toml` and run `poetry lock` in the affected service(s) to keep Docker builder deterministic.

12) Quick run checklist (local dev)
- Ensure `.env` contains `LLM_PROVIDER`, `LANGFUSE_HOST`, and any LLM API keys needed.
- Start infra: `docker compose up --build -d`.
- Confirm MCP/tools: `docker compose logs tool_pool_api --tail=50` and `docker compose logs atendente_core --tail=50`.
- Run a quick chat: `make chat` (uses API key from seeded DB).
- Generate traces: `make batch-run` (runs inside container and writes traces to Langfuse).

If you'd like, I can (a) run a dependency audit across `libs/` to detect duplicated or mismatched versions, (b) add CI checks to validate `poetry.lock` consistency for libs, or (c) open a PR with further docs and small refactors. Which would you prefer next?
