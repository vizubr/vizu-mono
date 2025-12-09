# Text-to-SQL Safe Execution Plan (Revised)

## Executive Summary
Build a secure, text-to-SQL query tool for Vizu that enforces multi-tenant isolation, view-only reads, and robust SQL validation via PostgREST under user JWT authentication and RLS policies.  The tool integrates with existing libs (vizu_supabase_client, vizu_sql_factory, vizu_prompt_management, vizu_llm_service) and leverages Supabase RLS as the primary security boundary.

---

## Phase 0: Audit, Discovery, and Scaffolding

### Objectives
1. Audit existing Supabase views and RLS policies to confirm text-to-SQL readiness.
2. Design and document the allowlist (views, columns, aggregates per tenant/role).
3. Build schema snapshot generator and safe introspection layer.
4.  Establish MCP tool contract and stub implementations.

### Key Tasks

#### 0.1 Audit Current RLS and Views
- **Action**: Enumerate all views in supabase/migrations/ and document RLS policies.
  - List all existing views, their purpose, and current RLS policies.
  - Identify which views are tenant-scoped (have client_id or equivalent tenant filter).
  - Identify gaps (views without RLS, views exposing sensitive columns, missing indices).
  - Document any views already used for client-facing reads.
- **Deliverable**: Audit report (markdown) in `docs/security/rls-audit.md` listing views, RLS status, and recommendations.
- **Test**: Manual review; cross-check with supabase/ migrations.

#### 0.2 Design and Freeze Allowlist Configuration
- **Action**: Define per-tenant and per-role allowlists in version control.
  - Create allowlist schema (JSON or Python dataclass):
    ```python
    {
      "tenant_id": ".. .",
      "roles": {
        "analyst": {
          "views": ["customers_view", "orders_view"],
          "columns": {"customers_view": ["id", "name", "created_at"], ... },
          "aggregates": ["COUNT", "SUM", "AVG"],
          "max_rows": 10000
        },
        "viewer": {
          "views": ["customers_view"],
          "columns": {"customers_view": ["id", "name"]},
          "aggregates": ["COUNT"],
          "max_rows": 1000
        }
      }
    }
    ```
  - Store allowlist in `libs/vizu_sql_factory/config/allowlist.json` (or env-driven).
  - Add migration hook: when schema changes, validate allowlist still matches.
- **Deliverable**:
  - `libs/vizu_sql_factory/config/allowlist.json` (example with 2–3 test tenants and roles).
  - `libs/vizu_sql_factory/allowlist. py`: `AllowlistConfig` dataclass and loader.
  - Unit test: `tests/test_allowlist.py` validates structure and role filtering.

#### 0.3 Build Schema Snapshot Generator
- **Action**: Create safe schema introspection that returns only allowed views/columns per role/tenant.
  - Implement `SchemaSnapshotGenerator` in `libs/vizu_sql_factory/schema_snapshot.py`:
    - Input: tenant_id, role, allowlist config.
    - Introspect Supabase information_schema (via PostgREST or direct query under service role with strict timeouts).
    - Filter by allowlist: return only allowed views and columns.
    - Include FK relationships (join paths).
    - Output: structured snapshot (JSON/dict) with views, columns, keys, sample data types.
    - Cache with TTL (e.g., 1 hour) to avoid on-every-request overhead.
  - **Handling schema introspection securely**:
    - Use `information_schema.tables`, `information_schema.columns` queries filtered to allowed views.
    - Prefer service role for introspection (not user JWT) but validate against allowlist *after* fetch.
    - Set query timeout (e.g., 5s) and row limit.
  - Unit test: mock Supabase responses; verify snapshot contains only allowed views/columns.
  - Integration test: real Supabase (or Docker-based test instance); compare with manual allowlist.

#### 0.4 Design Robust SQL Validation Layer (Scaffolding)
- **Action**: Establish interfaces and error types for validation.
  - Create `libs/vizu_sql_factory/validator.py` with stub implementations:
    - `SqlValidator` class with methods: `parse()`, `validate()`, `rewrite()`, `explain()`.
    - `ValidationError` and `ValidationResult` types (dataclasses):
      ```python
      @dataclass
      class ValidationResult:
        is_valid: bool
        original_sql: str
        normalized_sql: Optional[str]  # rewritten if applicable
        errors: List[ValidationError]
        warnings: List[str]
        checks_passed: List[str]
        execution_plan: Optional[str]  # for observability
      ```
    - Stub checks (no-op for now):
      - `check_only_allowed_views()`
      - `check_no_ddl_dml()`
      - `check_mandatory_predicates()`
      - `check_limit_present()`
      - `check_column_allowlist()`
    - Rewrite stubs: `rewrite_select_star()`, `rewrite_inject_limit()`, `rewrite_inject_tenant_filter()`.
  - Error handling: distinguish between parsing failures (soft-fail) and validation failures (block).
- **Deliverable**:
  - `libs/vizu_sql_factory/validator.py` with types and method signatures.
  - Unit test skeleton: `tests/test_validator. py` with placeholder test cases.

#### 0.5 Wire Supabase Client for PostgREST + JWT
- **Action**: Enhance `libs/vizu_supabase_client` with JWT-aware execution and pagination.
  - Review existing vizu_supabase_client implementation.
  - Add/extend `PostgRESTQueryExecutor` class:
    - Input: view name, filters (dict), limit, offset, user JWT.
    - Execute via PostgREST `/rest/v1/<view>` endpoint with user JWT in Authorization header.
    - Enforce limit cap (e.g., max 100 rows per request, configurable per tenant).
    - Add retry logic (exponential backoff, max 3 retries) for transient failures.
    - Timeout: 30s default.
    - Return: rows, column metadata, count.
  - Add `AuthContext` helper:
    - Extract tenant_id, role from JWT claims.
    - Validate claims structure (expected fields).
  - Test: Integration test against test Supabase instance; verify RLS enforcement (401/403 on disallowed data).
- **Deliverable**:
  - Enhanced `libs/vizu_supabase_client/postgrest_client.py`.
  - `libs/vizu_supabase_client/auth_context.py` with JWT parsing.
  - Integration test: `tests/test_postgrest_execution.py` with fixture tenant/role data.

#### 0. 6 Register MCP Tool Skeleton
- **Action**: Define tool contract in vizu_tool_registry.
  - Add `libs/vizu_tool_registry/tools/sql_tool.py` with:
    - Tool name: `query_database_text_to_sql` or `execute_analytics_query`.
    - Inputs:
      - `question: str` — user's natural language query.
      - `tenant_id: str` — for context (extracted from JWT at runtime).
      - `role: str` — user's role.
      - `optional_constraints: Dict` — e.g., `{"date_range": "last_30_days", "max_rows": 100}`.
    - Outputs:
      - `success: bool`
      - `sql: str` — validated SQL or null if failed.
      - `rows: List[Dict]` — query results or empty.
      - `columns: List[Dict]` — column metadata (name, type).
      - `caveats: List[str]` — e.g., "Result limited to 100 rows", "Cross-tenant queries blocked".
      - `error: Optional[Dict]` — structured error if failed; includes error code, message, suggestion.
      - `telemetry_id: str` — UUID for tracing logs.
    - Register in registry with stable schema and versioning.
  - Placeholder implementation: returns fixed mock result.
- **Deliverable**:
  - `libs/vizu_tool_registry/tools/sql_tool.py` with tool definition and registry entry.
  - Mock integration test: `tests/test_sql_tool_registration.py`.

### Implementation Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Allowlist misconfiguration (overly permissive or incomplete) | Require code review + automated schema diff on migrations; fail CI if allowlist not updated. |
| Schema introspection breaks due to Supabase API changes | Use versioned Supabase Python client; add feature detection (introspection via `information_schema` fallback). |
| RLS policies missing or incorrect on existing views | Audit in Phase 0 Task 0.1; add RLS policy templates to migrations; enforce via migration tests. |
| JWT claims don't contain expected fields (tenant_id, role) | Define JWT schema in docs; add strict validation with descriptive errors; fail fast.  |
| PostgREST timeout/rate limits block execution | Add circuit breaker; tune timeout and batch sizes; monitor latency; alert on degradation. |

### Phase 0 Checklist
- [ ] Audit report documents all views, RLS status, gaps (Task 0.1).
- [ ] Allowlist config (allowlist.json, AllowlistConfig class) defined and frozen (Task 0.2).
- [ ] Schema snapshot generator returns allowed views/columns per role/tenant (Task 0. 3).
- [ ] Validator interface and error types established; stubs in place (Task 0.4).
- [ ] Supabase client supports JWT-aware PostgREST queries with pagination and retries (Task 0.5).
- [ ] MCP tool registered with documented schema; mock returns fixed result (Task 0.6).
- [ ] CI enforces allowlist validation on schema migrations.

### Phase 0 Checkpoints with Tests

**Unit Tests**
1. `test_allowlist_filter_by_role()`: Verify allowlist returns correct subset given role/tenant.
2. `test_schema_snapshot_excludes_disallowed_views()`: Mock Supabase schema; snapshot excludes non-allowed views.
3. `test_auth_context_extracts_jwt_claims()`: Parse JWT; extract tenant_id and role correctly.
4. `test_validator_error_types()`: Verify ValidationResult structure and error serialization.
5. `test_sql_tool_returns_expected_schema()`: Tool definition matches documented inputs/outputs.

**Integration Tests**
6. `test_postgrest_query_with_user_jwt()`: Execute a simple query via PostgREST using user JWT; verify results.
7. `test_postgrest_denies_disallowed_view()`: Query disallowed view via PostgREST; expect 403 or empty result.
8. `test_schema_snapshot_generator_real_supabase()`: Query real test Supabase; snapshot matches allowlist.
9. `test_mcp_tool_registers_and_returns_mock()`: MCP tool callable; returns mock result with correct structure.

**Approval Gate**: All Phase 0 tests passing; audit report reviewed by security lead; allowlist finalized.

---

## Phase 1: Prompting and Constraints

### Objectives
1. Build deterministic, constraint-driven prompt templates.
2. Integrate schema snapshots and allowlist into prompt assembly.
3. Configure LLM calls with safety parameters (temperature, output format).
4. Establish exemplars and validation guardrails.

### Key Tasks

#### 1.1 Build Prompt Templates
- **Action**: Create reusable prompt templates in `libs/vizu_prompt_management/templates/text_to_sql. md`.
  - **System prompt**:
    ```
    You are an expert SQL analyst.  Your task is to translate a user's natural language question into a safe, read-only SQL query.

    CONSTRAINTS (non-negotiable):
    1. Return ONLY valid PostgreSQL SELECT statements.  No comments, explanations, or text outside the query.
    2. Use ONLY the views and columns listed in the schema below.  Do NOT reference base tables, materialized views not listed, or columns marked hidden.
    3. Every query MUST include a filter predicate for the tenant identifier (e.g., WHERE client_id = <tenant_id>).  This is automatic and will be injected if missing, so assume it exists.
    4. Explicitly list all columns in the SELECT clause.  Never use SELECT * or SELECT table. *.
    5. Always include a LIMIT clause.  Default to LIMIT 100; the maximum allowed is <max_rows_per_tenant>.
    6. Do NOT use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or any DDL/DML.  SELECT-only.
    7. Joins are allowed only via the foreign keys listed below. No cross-tenant joins.
    8.  Aggregates allowed: COUNT, SUM, AVG, MIN, MAX.  No user-defined functions.
    9.  If the question cannot be answered within these constraints, respond with the word UNABLE followed by a brief reason on the same line.  Example: UNABLE question asks for a union of two cross-tenant datasets which violates isolation rules.

    SCHEMA (filtered for your role):
    <schema_snapshot>

    EXEMPLARS (safe queries matching constraints):
    <exemplars>

    USER QUESTION:
    <question>
    ```
  - **Schema snapshot block**: Include views, columns, sample join paths, and tenant/role context.
  - **Exemplars block**: 2–4 representative queries demonstrating:
    - Mandatory tenant filter.
    - Explicit column selection.
    - LIMIT clause.
    - Common joins.
    - Simple aggregation (e.g., `SELECT COUNT(*) FROM orders_view WHERE client_id = :tenant_id LIMIT 1`).
  - **Constraints block** (optional, separate file): Enumerate limits (max_rows, max_execution_time, disallowed functions).
- **Deliverable**:
  - `libs/vizu_prompt_management/templates/text_to_sql.md` with system + exemplar sections.
  - `libs/vizu_prompt_management/templates/constraints.json` with configurable limits per tenant/role.
  - `libs/vizu_prompt_management/prompt_builder.py`:
    - `TextToSqlPromptBuilder` class.
    - Methods: `build(question, tenant_id, role, schema_snapshot, constraints) -> str`.
    - Interpolates schema, exemplars, and constraints into template.

#### 1.2 Integrate Prompt Assembly with Context
- **Action**: Wire schema snapshots and tenant context into prompt builder.
  - `PromptBuilder. build()` should:
    - Accept `TenantContext` (tenant_id, role, claims).
    - Fetch or use cached schema snapshot (via SchemaSnapshotGenerator from Phase 0).
    - Load allowlist and constraints (from AllowlistConfig).
    - Assemble final prompt string.
  - Add optional constraints refinement (e.g., user-provided date_range narrows schema snapshot to relevant date columns).
  - Unit test: mock schema snapshot; verify prompt includes only allowed views and exemplars.
- **Deliverable**:
  - Enhanced `libs/vizu_prompt_management/prompt_builder.py` with context integration.
  - Unit test: `tests/test_prompt_builder_integration.py`.

#### 1. 3 Configure LLM Call Parameters
- **Action**: Define deterministic LLM config for SQL generation.
  - In `libs/vizu_llm_service/text_to_sql_config.py` or equiv.:
    - Model: e.g., `gpt-4-turbo`, `claude-3-sonnet` (configurable).
    - Temperature: `0.0` (deterministic; no creativity).
    - Max tokens: `500` (SQL queries are typically short).
    - Stop tokens: `["UNABLE", ";", "\n\n"]` (prevent hallucination after query).
    - Retry policy: exponential backoff, max 3 attempts.
    - Timeout: 30s.
  - Implement `TextToSqlLLMCall` wrapper:
    - Input: assembled prompt (from PromptBuilder).
    - Output: raw LLM response.
    - Post-process: extract SQL (between stop tokens, trim whitespace).
  - Add output parser / validator (Phase 2 will enhance):
    - Check response is non-empty and contains `SELECT`.
    - Reject responses containing `UNABLE` early (don't proceed to validation).
- **Deliverable**:
  - `libs/vizu_llm_service/text_to_sql_config.py` with LLM parameters.
  - `libs/vizu_llm_service/text_to_sql_call.py` with LLM call wrapper and output parsing.
  - Unit test: `tests/test_llm_output_parsing.py` (mock LLM responses).

#### 1.4 Build Exemplar Dataset and Validation Harness
- **Action**: Create a fixture corpus of questions and expected safe SQL.
  - Define test questions per role/tenant (e.g., "List all orders for the past 30 days with customer name and total"):
    - Provide expected SQL (schema-aware, includes mandatory predicates, limits).
    - Expected result schema.
  - Store in `tests/fixtures/exemplars.json` or YAML.
  - Build validation harness in `tests/test_exemplars.py`:
    - For each exemplar, run LLM call and compare output to expected SQL (or semantic equivalence via AST comparison).
    - Track hallucination rate (e.g., "X% of queries generated disallowed tables").
  - Example fixture entry:
    ```json
    {
      "tenant_id": "tenant_123",
      "role": "analyst",
      "question": "How many orders were placed this month?",
      "expected_sql": "SELECT COUNT(*) AS order_count FROM orders_view WHERE client_id = 'tenant_123' AND created_at >= '2025-12-01' LIMIT 100",
      "expected_columns": ["order_count"]
    }
    ```
- **Deliverable**:
  - `tests/fixtures/exemplars.json` with 10–20 test cases (various roles/tenants).
  - `tests/test_exemplars.py` with LLM call harness and validation logic.

### Implementation Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM hallucinating disallowed tables | Strict system prompt with constraints repeated; exemplars showing only-allowed views; Phase 2 validator catches misses. |
| Prompt token limit exceeded on large schemas | Implement schema summarization (include only relevant views based on question keyword match); cache schemas.  |
| Temperature 0. 0 too restrictive; LLM refuses some valid queries | Increase temperature to 0.1–0.2 if hallucination rate is low; A/B test on exemplars. |
| Exemplars become stale as schema changes | Automate exemplar validation in CI; regenerate on schema drift. |

### Phase 1 Checklist
- [ ] Prompt template (text_to_sql.md) includes system, schema, exemplars, constraints.
- [ ] PromptBuilder integrates with schema snapshot and tenant context.
- [ ] LLM call config (temperature, timeout, stop tokens) is deterministic and documented.
- [ ] Exemplar corpus (10–20 test cases) defined and validated.
- [ ] Output parser rejects non-SQL responses and responses containing UNABLE.

### Phase 1 Checkpoints with Tests

**Unit Tests**
1. `test_prompt_builder_includes_allowed_views()`: Verify schema snapshot in prompt contains only allowed views.
2. `test_prompt_builder_injects_exemplars()`: Prompt includes exemplars; exemplars show mandatory predicates and limits.
3. `test_llm_output_parser_accepts_valid_sql()`: Parser accepts well-formed SELECT statements.
4. `test_llm_output_parser_rejects_non_sql()`: Parser rejects non-SQL content, DDL/DML, or responses with UNABLE.
5. `test_constraints_applied_per_role()`: Different roles get different max_rows, aggregate limits, etc.  in prompt.

**Integration/Manual Tests**
6. `test_exemplar_corpus_llm_generation()`: For each test exemplar, call LLM; measure hallucination and SQL quality (manual review of 5–10 samples).
7. `test_prompt_builder_with_real_schema()`: Use real test Supabase schema; verify prompt is syntactically valid and includes correct views.

**Approval Gate**: Exemplar corpus reviewed by domain expert; hallucination rate <5%; all prompt template tests passing.

---

## Phase 2: SQL Validation and Guardrails

### Objectives
1. Implement robust SQL parser and validator.
2. Enforce checks for allowed views, mandatory predicates, limits, and safe constructs.
3. Add optional rewrites for normalization and safety.
4. Establish observability for validation decisions.

### Key Tasks

#### 2.1 Choose and Integrate SQL Parser
- **Action**: Select and integrate a production-grade SQL parser library.
  - Candidate: `sqlglot` (Python, handles PostgreSQL dialect, good error recovery).
    - Pros: Parses to AST, supports rewrites, dialect-aware, actively maintained.
    - Cons: Large dependency; some edge cases with Postgres-specific syntax (JSON operators, window functions).
  - Alternative: `sqlparse` (simpler, lexical, less robust but adequate for basic validation).
  - Decision: Use `sqlglot` for Phase 2+; fallback to lexical checks if parse fails.
  - Add `sqlglot` to `libs/vizu_sql_factory/pyproject.toml`.
- **Deliverable**:
  - `libs/vizu_sql_factory/parser.py` with `SqlParser` wrapper:
    - `parse(sql_string) -> Union[ast.Select, ParseError]`.
    - Graceful error handling; log unparseable queries for monitoring.

#### 2.2 Implement Core Validation Checks
- **Action**: Implement validators in `libs/vizu_sql_factory/validator.py`.
  - **Check: Only Allowed Views**
    - Extract all table/view references from AST.
    - Cross-check against allowlist.
    - Reject if any disallowed view found.
    - Unit test: parse SQL with disallowed table; expect validation error.
  - **Check: No DDL/DML**
    - Verify AST is a SELECT statement.
    - Reject INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, etc.
    - Unit test: parse DDL; expect rejection.
  - **Check: Mandatory Predicates**
    - Extract WHERE clause predicates.
    - Verify presence of tenant filter (e.g., `client_id = <value>` or `client_id IN (... )`).
    - **Caveat**: Dynamic predicates (e.g., variables in query string) are hard to validate statically; log as warning, allow if user context is known.
    - Rewrite rule (Phase 2. 3): inject tenant filter if deterministically known and missing.
    - Unit test: query without client_id filter; expect validation error or rewrite flag.
  - **Check: Explicit Columns**
    - Reject `SELECT *` or `SELECT table.*`.
    - Verify all selected columns are in allowlist.
    - Rewrite rule: expand `SELECT *` to explicit columns (Phase 2.3).
    - Unit test: `SELECT * FROM orders_view`; expect rewrite or rejection.
  - **Check: LIMIT Present**
    - Verify LIMIT clause exists.
    - Verify LIMIT value ≤ max_rows for tenant/role.
    - Rewrite rule: inject LIMIT if missing or too high (Phase 2.3).
    - Unit test: query without LIMIT; expect rewrite or rejection.
  - **Check: Column Allowlist**
    - Compare selected columns against allowlist for each view.
    - Reject if any column not in allowlist (e.g., hidden PII columns).
    - Unit test: select a hidden column; expect rejection.
  - **Check: Safe Joins (Optional for Phase 2. 2)**
    - Extract JOIN predicates.
    - Verify joins use only allowed FK relationships (documented in schema snapshot).
    - Reject cross-tenant joins.
    - Unit test: cross-tenant join; expect rejection.
  - **Check: Safe Aggregates (Optional)**
    - Allowed: COUNT, SUM, AVG, MIN, MAX.
    - Reject: user-defined functions, window functions (unless explicitly allowed per role).
    - Unit test: query with PERCENTILE_CONT(); expect rejection if not allowed.
  - All checks return `ValidationResult` (from Phase 0.4).
- **Deliverable**:
  - `libs/vizu_sql_factory/validator. py` with `SqlValidator` class and check methods.
  - `libs/vizu_sql_factory/checks.py` with individual check implementations.
  - Unit tests: `tests/test_validator_checks.py` with 15+ test cases (good/bad queries).

#### 2. 3 Implement Rewrites
- **Action**: Add optional SQL normalization and safety rewrites.
  - **Rewrite: Expand SELECT \***
    - Replace `SELECT *` with explicit column list from allowlist.
    - Preserve column order; add aliases if needed.
    - Unit test: `SELECT * FROM orders_view` → `SELECT id, customer_id, amount, created_at FROM orders_view`.
  - **Rewrite: Inject LIMIT**
    - If LIMIT missing, append `LIMIT <max_rows>`.
    - If LIMIT present but > max_rows, replace with capped value.
    - Unit test: `SELECT ...  LIMIT 10000` with max_rows=100 → capped to 100.
  - **Rewrite: Inject Tenant Filter**
    - If tenant_id is known from context and WHERE clause lacks tenant predicate, inject `AND client_id = <tenant_id>`.
    - Only do this if deterministically known (i.e., single-tenant query from user JWT).
    - Reject if ambiguous (multi-tenant context or dynamic filters).
    - Unit test: query without client_id filter; inject if tenant_id provided.
  - Config option: `allow_rewrites` (boolean per check or globally).
    - If enabled, attempt rewrites; return normalized_sql in ValidationResult.
    - If disabled, validation fails instead of rewriting.
    - Default: enabled for Phase 2 testing; can disable in production for strict validation.
- **Deliverable**:
  - `libs/vizu_sql_factory/rewrites.py` with rewrite implementations.
  - Unit tests: `tests/test_validator_rewrites.py`.

#### 2.4 Add Observability and Explain Mode
- **Action**: Log validation decisions for auditing and debugging.
  - Extend `ValidationResult` with:
    - `checks_performed: List[str]` — list of checks run.
    - `checks_passed: List[str]` — checks that passed.
    - `checks_failed: List[ValidationError]` — detailed errors.
    - `execution_plan: str` — human-readable summary (e.g., "Validation: OK.  Rewrites: expand SELECT *, inject LIMIT. Final SQL has 2 joins, 1 aggregation, client_id filter present. ").
  - Implement explain-only mode:
    - Run all checks, log results, but don't block execution.
    - Useful for observability and tuning allowlists.
    - Add flag: `explain_only=True` to validator.
  - Emit structured logs (JSON) with:
    - Timestamp, tenant_id, role, question_hash (to avoid PII), original SQL, normalized SQL, validation result, execution time.
    - Send to observability backend (vizu_observability_bootstrap).
  - Unit test: verify ValidationResult includes all fields; check log output.
- **Deliverable**:
  - Enhanced `libs/vizu_sql_factory/validator.py` with observability hooks.
  - `libs/vizu_sql_factory/observability.py` with logging and structured telemetry.
  - Unit test: `tests/test_validator_observability.py`.

#### 2.5 Validate Against Exemplars
- **Action**: Run Phase 1 exemplar corpus through validator.
  - For each exemplar, validate expected SQL.
  - Confirm validator passes expected queries and rejects clearly unsafe ones.
  - Measure false positive rate (safe queries rejected) and false negatives (unsafe queries accepted).
  - Document any deviations; adjust allowlist or rewrite rules.
- **Deliverable**:
  - Integration test: `tests/test_validator_exemplars.py`.

### Implementation Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Parser fails on edge cases (Postgres-specific syntax) | Use sqlglot (robust); add fallback lexical checks; log parse failures; design validator to be lenient on parse errors (better to miss a bad query than block good ones). |
| Rewrites change query semantics | Use AST-based rewrites (not string manipulation); add unit tests for each rewrite; manual review of rewritten queries. |
| False positives: validator rejects legitimate queries | Maintain allowlist rigorously; add developer feedback loop (log rejected queries, review weekly). |
| Tenant filter injection ambiguous or missing | Only inject if context unambiguously known; otherwise reject with clear error message. |

### Phase 2 Checklist
- [ ] SQL parser integrated and tested (sqlglot or alternative).
- [ ] Core checks implemented: allowed views, no DDL/DML, explicit columns, LIMIT, column allowlist.
- [ ] Optional checks (joins, aggregates) scoped and documented.
- [ ] Rewrites implemented: SELECT *, LIMIT, tenant filter.
- [ ] Observability: validation decisions logged with structured telemetry.
- [ ] Validator passes Phase 1 exemplars; false positive/negative rates acceptable.

### Phase 2 Checkpoints with Tests

**Unit Tests**
1. `test_validator_parse_select_statement()`: Parse valid SELECT; AST extracted.
2. `test_validator_rejects_disallowed_view()`: Validator rejects query referencing non-allowed view.
3. `test_validator_rejects_ddl()`: Validator rejects INSERT, UPDATE, DELETE, CREATE, etc.
4. `test_validator_rejects_missing_limit()`: Query without LIMIT fails validation (or is rewritten).
5. `test_validator_rejects_missing_tenant_filter()`: Query without client_id filter fails (or is rewritten if tenant known).
6. `test_validator_rejects_select_star()`: `SELECT *` is rewritten to explicit columns or rejected.
7. `test_validator_rejects_disallowed_column()`: Query selecting hidden column is rejected.
8. `test_validator_rejects_cross_tenant_join()`: Join predicate crossing tenant boundaries is rejected.
9.  `test_validator_accepts_safe_query()`: Well-formed query with all constraints passes.
10. `test_validator_rewrite_select_star()`: `SELECT * FROM orders_view` → `SELECT id, customer_id, amount ...  FROM orders_view`.
11.  `test_validator_rewrite_inject_limit()`: Query without LIMIT → injected with max_rows.
12. `test_validator_rewrite_inject_tenant_filter()`: Query without tenant filter + known tenant_id → injected filter.
13. `test_validator_observability_logs_validation_result()`: Validation result includes all telemetry fields.
14. `test_validator_explain_only_mode()`: explain_only=True returns result without blocking.

**Integration Tests**
15. `test_validator_against_exemplar_corpus()`: Run all Phase 1 exemplars through validator; measure false positive/negative rates.
16. `test_validator_with_real_schema()`: Use real test Supabase schema; validate queries work end-to-end.

**Security Tests**
17. `test_validator_security_fuzz()`: Feed validator a corpus of adversarial queries (injection attempts, cross-tenant queries, DDL, etc. ); expect all to be blocked.

**Approval Gate**: False positive rate <2%; false negative rate <5%; security fuzz tests all passing; code review by security lead.

---

## Phase 3: Execution and Result Handling (PostgREST under RLS)

### Objectives
1.  Execute validated SQL via PostgREST using user JWT.
2. Enforce pagination, timeouts, and result sanitization.
3.  Implement observability for execution lineage.

### Key Tasks

#### 3.1 Implement Query Executor
- **Action**: Build executor in `libs/vizu_sql_factory/executor.py`.
  - `TextToSqlExecutor` class:
    - Input: validated SQL (from Phase 2 validator), tenant_id, role, user JWT.
    - Delegate to `libs/vizu_supabase_client/postgrest_client.py` (wired in Phase 0).
    - Handle execution errors:
      - 401/403: authentication/authorization failure (RLS denial) → return structured error.
      - Timeout: query took too long → return error with suggestion (e.g., "Try a narrower date range").
      - Connection error: Supabase unavailable → retry with backoff; return error after max retries.
    - Return: `ExecutionResult` (dataclass):
      ```python
      @dataclass
      class ExecutionResult:
        success: bool
        rows: List[Dict]
        columns: List[Dict]  # name, type
        row_count: int
        execution_time_ms: float
        error: Optional[ExecutionError]  # if failed
        telemetry_id: str  # UUID for tracing
      ```
  - Pagination:
    - Input: limit (already enforced by validator), offset (default 0).
    - Return stable order (e.g., ORDER BY id if not already present) for consistent pagination.
    - Return: row_count, total_count (if available).
  - Timeout: enforce per-tenant timeout (e.g., 30s); tune based on typical query complexity.
- **Deliverable**:
  - `libs/vizu_sql_factory/executor. py` with `TextToSqlExecutor` and `ExecutionResult`.
  - Unit test: mock PostgREST responses; test error handling and pagination.
  - Integration test: execute validated queries against test Supabase.

#### 3.2 Result Sanitization
- **Action**: Implement result filtering to respect column allowlist and prevent PII leakage.
  - `ResultSanitizer` class in `libs/vizu_sql_factory/sanitizer.py`:
    - Input: raw rows from PostgREST, column allowlist.
    - Remove/filter columns not in allowlist (e.g., hidden fields, PII).
    - Optionally redact sensitive values (e.g., email → "***@***.com").
    - Normalize data types (timestamps, decimals) for consistent client rendering.
    - Output: sanitized rows and column metadata.
  - **Caveat**: Validator already filters at query level; sanitizer is defense-in-depth.
  - Unit test: mock result set with hidden columns; verify sanitizer removes them.
- **Deliverable**:
  - `libs/vizu_sql_factory/sanitizer.py` with `ResultSanitizer` class.
  - Unit test: `tests/test_result_sanitizer.py`.

#### 3.3 Wire Execution into MCP Tool
- **Action**: Integrate executor into MCP tool pipeline.
  - In `libs/vizu_tool_registry/tools/sql_tool.py`:
    - LLM call (Phase 1) → Validator (Phase 2) → Executor (Phase 3) → Sanitizer (Phase 3. 2) → MCP tool output.
    - Full orchestration: `TextToSqlTool. execute(question, tenant_id, role, user_jwt, constraints)`.
    - Return MCP tool output structure (from Phase 0. 6).
  - Error handling:
    - LLM returns UNABLE → return structured error (code: `llm_unable`).
    - Validator fails → return structured error (code: `validation_failed`, include suggestions).
    - Executor fails (RLS denial) → return structured error (code: `rls_denied`).
    - Executor fails (timeout) → return structured error (code: `execution_timeout`).
  - All errors include `caveats` and optional `suggestion` for user refinement.
- **Deliverable**:
  - Enhanced `libs/vizu_tool_registry/tools/sql_tool.py` with full pipeline.
  - Integration test: `tests/test_sql_tool_end_to_end.py` (LLM → validator → executor).

#### 3.4 Observability and Telemetry
- **Action**: Emit structured logs tracking query lineage.
  - Integration with `vizu_observability_bootstrap`:
    - Log entry for each execution with:
      - `telemetry_id` (UUID, consistent across LLM → validator → executor).
      - `tenant_id`, `role` (from JWT).
      - `original_question_hash` (hash of user question, no PII).
      - `llm_model`, `llm_tokens_used`.
      - `original_sql`, `validated_sql`, `execution_time_ms`, `row_count`.
      - `validation_checks_passed`, `validation_checks_failed`.
      - Outcome: success, validation_failed, rls_denied, timeout, etc.
    - Allow linking logs from question through execution.
  - Add tracing:
    - Trace IDs propagated through tool calls.
    - Enable debugging of multi-step failures.
  - Add metrics:
    - Latency histogram per step (LLM, validation, execution).
    - Success rate per tenant/role.
    - Validation pass rate.
    - RLS denial rate (should be near 0 if allowlist is correct).
- **Deliverable**:
  - `libs/vizu_sql_factory/telemetry.py` with logging and metrics.
  - Integration with observability bootstrap.
  - Unit test: verify telemetry fields populated.

#### 3.5 Multi-Tenant Data Isolation Testing
- **Action**: Comprehensive isolation tests to verify no cross-tenant data leakage.
  - Test design:
    - Create 2+ test tenants with overlapping data (e.g., shared reference tables).
    - For each tenant, run allowed queries; verify results include only tenant-scoped data.
    - Attempt cross-tenant queries (e.g., explicit WHERE clause with different tenant_id).
    - Expect RLS to block (403) or return empty.
  - Test cases:
    - Query as tenant A; verify rows only have client_id = A.
    - Query as tenant B with different allowlist; verify only B's allowed views are accessible.
    - Attempt SELECT * FROM base_table (not in allowlist); expect validator to reject.
    - Attempt cross-tenant join; expect validator to reject or RLS to deny.
  - Frequency: run after schema changes or allowlist updates.
- **Deliverable**:
  - `tests/test_multi_tenant_isolation.py` with comprehensive isolation tests.

### Implementation Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| PostgREST cannot execute complex queries (no support for CTEs, window functions) | Ensure all test queries fit PostgREST constraints; use views to abstract complexity; add pre-check in validator that flags unsupported constructs. |
| RLS policies misconfigured; PostgREST allows unintended data access | Audit RLS policies (Phase 0); add explicit tests for each policy; use service-role queries only for introspection, never for user data. |
| Pagination inconsistent (rows skipped or duplicated); instability in sorting | Enforce deterministic ORDER BY (e.g., by primary key) in rewrite or validator; use stable offset-based pagination; test with realistic dataset sizes. |
| Result sanitizer strips legitimate columns due to allowlist misconfiguration | Keep sanitizer logic minimal; rely on allowlist; log sanitization events; alert on excessive filtering. |
| Performance hotspots: complex queries timeout; need materialized views/indices | Monitor execution times per query; identify slow queries; propose indices or materialized views; test before deploying. |

### Phase 3 Checklist
- [ ] Executor orchestrates validation and PostgREST execution with error handling.
- [ ] Result sanitizer filters columns per allowlist; defense-in-depth against PII leakage.
- [ ] MCP tool integrates full pipeline (LLM → validator → executor → sanitizer).
- [ ] Structured error handling: validation_failed, rls_denied, timeout, etc.
- [ ] Observability: telemetry IDs, lineage logs, metrics per step.
- [ ] Multi-tenant isolation tests confirm no data leakage across tenants.

### Phase 3 Checkpoints with Tests

**Unit Tests**
1. `test_executor_handles_postgrest_success()`: Mock successful PostgREST response; executor returns ExecutionResult with rows.
2. `test_executor_handles_rls_denial()`: Mock 403 RLS denial; executor returns structured error (code: rls_denied).
3. `test_executor_handles_timeout()`: Mock timeout; executor retries and returns error after max retries.
4. `test_executor_enforces_pagination_cap()`: Input limit > max_rows; executor enforces cap.
5. `test_result_sanitizer_removes_disallowed_columns()`: Mock result with hidden columns; sanitizer removes them.
6. `test_result_sanitizer_normalizes_data_types()`: Timestamps, decimals normalized.

**Integration Tests**
7. `test_sql_tool_end_to_end_question_to_results()`: Full pipeline: question → LLM → validator → executor → results.
8. `test_sql_tool_handles_validation_failure()`: Question leads to validation error; tool returns structured error.
9. `test_sql_tool_handles_rls_denial()`: User without access to view; tool returns rls_denied error.
10.  `test_sql_tool_observability_telemetry_complete()`: Execution produces telemetry with all expected fields.

**Security/Isolation Tests**
11. `test_multi_tenant_isolation_queries_as_tenant_a()`: Tenant A queries; results only include A's data.
12. `test_multi_tenant_isolation_queries_as_tenant_b()`: Tenant B queries; results only include B's data.
13. `test_multi_tenant_isolation_cross_tenant_attempt()`: Attempt cross-tenant query; validator or RLS blocks.
14. `test_multi_tenant_isolation_allowlist_mismatch()`: Tenant A tries to query view not in allowlist; validator rejects.

**Performance Tests**
15. `test_execution_latency_typical_query()`: Execute representative queries; latency <1s.
16. `test_execution_large_result_pagination()`: Query with many rows; pagination stable and complete.

**Approval Gate**: All multi-tenant isolation tests passing; no data leakage across tenants; performance baseline established; security review approval.

---

## Phase 4: MCP Tool Integration and UX

### Objectives
1.  Finalize MCP tool definition and registration.
2. Implement comprehensive error handling and user guidance.
3. Provide developer docs and examples.

### Key Tasks

#### 4.1 Finalize MCP Tool Schema and Registration
- **Action**: Complete tool definition in `libs/vizu_tool_registry/tools/sql_tool.py`.
  - Tool name: `query_database_analytics` or `execute_text_to_sql_query` (finalize per design).
  - Inputs (JSON Schema):
    ```json
    {
      "question": {
        "type": "string",
        "description": "Natural language question about the data (e.g., 'How many orders were placed last month?')"
      },
      "tenant_id": {
        "type": "string",
        "description": "Tenant identifier (extracted from user JWT; can be overridden for testing)"
      },
      "role": {
        "type": "string",
        "description": "User's role (e.g., 'analyst', 'viewer') determining schema access"
      },
      "optional_constraints": {
        "type": "object",
        "description": "Optional filters to narrow scope (e.g., {'date_range': 'last_30_days', 'max_rows': 100})",
        "properties": {
          "date_range": {"type": "string", "enum": ["today", "last_7_days", "last_30_days", "last_year", "custom"]},
          "custom_date_range": {"type": "object", "properties": {"start_date": {"type": "string"}, "end_date": {"type": "string"}}},
          "columns_to_include": {"type": "array", "items": {"type": "string"}},
          "max_rows": {"type": "integer", "minimum": 1}
        }
      }
    }
    ```
  - Outputs (JSON Schema):
    ```json
    {
      "success": {
        "type": "boolean",
        "description": "True if query executed successfully; false if failed"
      },
      "sql": {
        "type": "string",
        "description": "The SQL query that was executed (or attempted)"
      },
      "rows": {
        "type": "array",
        "description": "Query result rows as list of objects"
      },
      "columns": {
        "type": "array",
        "description": "Column metadata: [{name, type, description}]"
      },
      "row_count": {
        "type": "integer",
        "description": "Number of rows returned"
      },
      "total_count": {
        "type": "integer",
        "description": "Total number of rows matching query (before pagination limit)"
      },
      "caveats": {
        "type": "array",
        "description": "Warnings or limitations (e.g., 'Result limited to 100 rows', 'Date range truncated to allowed views')"
      },
      "error": {
        "type": "object",
        "description": "Structured error if failed",
        "properties": {
          "code": {"type": "string", "enum": ["llm_unable", "validation_failed", "rls_denied", "execution_timeout", "schema_unavailable", "internal_error"]},
          "message": {"type": "string", "description": "Human-readable error message"},
          "suggestion": {"type": "string", "description": "Hint for user to refine query"}
        }
      },
      "telemetry_id": {
        "type": "string",
        "description": "UUID for tracing this query in logs"
      }
    }
    ```
  - Register in vizu_tool_registry with versioning (e.g., v1).
- **Deliverable**:
  - `libs/vizu_tool_registry/tools/sql_tool.py` with finalized schema and registration.
  - Schema documentation in code comments.

#### 4.2 Implement Graceful Error Handling
- **Action**: Enrich error messages and suggestions.
  - Error code: `llm_unable`
    - Message: "The AI language model was unable to formulate a query.  This may indicate the question is outside the scope of available data or is too ambiguous."
    - Suggestion: "Try rephrasing your question more specifically (e.g., include date range, specific metrics)."
  - Error code: `validation_failed`
    - Message: "The generated SQL does not meet safety constraints.  [Specific reason: e.g., 'Query references a disallowed view (base_customers_table)']."
    - Suggestion: "Available views for your role are: [list].  Try asking about those instead."
  - Error code: `rls_denied`
    - Message: "Access to the requested data is denied by security policies."
    - Suggestion: "You may not have permission to view this data in your role. Contact your administrator if this is unexpected."
  - Error code: `execution_timeout`
    - Message: "Query execution timed out after 30 seconds."
    - Suggestion: "Try narrowing the query scope (e.g., specific date range, fewer rows, fewer joins)."
  - Error code: `schema_unavailable`
    - Message: "Schema metadata is temporarily unavailable."
    - Suggestion: "Try again in a moment. If the issue persists, contact support."
  - Error code: `internal_error`
    - Message: "An internal error occurred."
    - Suggestion: "Please contact support with telemetry ID: [telemetry_id]."
  - All errors include `telemetry_id` for debugging without revealing logs to user.
- **Deliverable**:
  - Enhanced error handling in `libs/vizu_tool_registry/tools/sql_tool.py`.
  - Unit test: `tests/test_sql_tool_error_messages.py`.

#### 4. 3 Provide Developer Documentation and Examples
- **Action**: Create comprehensive docs in `docs/text_to_sql/` directory.
  - **README. md**:
    - Overview of tool purpose, security model, and constraints.
    - Quick start: example invocation, expected output.
  - **USAGE.md**:
    - Tool signature and parameter descriptions.
    - Example use cases:
      - Simple aggregation (e.g., "Count orders by status").
      - Joins (e.g., "Show customer orders with amounts").
      - Date filtering (e.g., "Orders from the past week").
      - Error scenarios and how to recover.
    - Sample JSON invocations and responses.
  - **SECURITY.md**:
    - Explanation of RLS, allowlist, and why queries may be rejected.
    - Mention of view-only reads and tenant isolation.
    - What data is visible per role.
    - How constraints (LIMIT, mandatory predicates) protect against runaway queries.
  - **TROUBLESHOOTING.md**:
    - Common error codes and solutions.
    - When to refine questions vs. contact support.
  - **EXAMPLES.md**:
    - 10+ worked examples for different roles/tenants.
    - Include expected SQL and result structure.
  - **FAQ.md**:
    - Why is my question rejected?
    - What views can I query?
    - How do I get access to more data?
- **Deliverable**:
  - `docs/text_to_sql/README.md`, `USAGE.md`, `SECURITY. md`, `TROUBLESHOOTING.md`, `EXAMPLES.md`, `FAQ.md`.
  - Example JSON files in `docs/text_to_sql/examples/` (request/response pairs).

#### 4.4 Implement Tool Testing Harness for Developers
- **Action**: Create an interactive testing tool for developers to validate tool behavior.
  - Script: `scripts/test_sql_tool.py` (or CLI command).
    - Takes a question as input.
    - Runs through full pipeline (LLM → validator → executor).
    - Outputs result or error with telemetry ID.
    - Useful for debugging allowlist, schema, and prompt issues.
  - Integration test suite:
    - Predefined test cases covering common scenarios and error conditions.
    - Can be run in CI or manually for validation.
- **Deliverable**:
  - `scripts/test_sql_tool.py` interactive testing script.
  - Integration test suite: `tests/test_sql_tool_integration_suite.py`.

### Implementation Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Error messages leak sensitive information (e.g., list of all available views) | Be generic in error messages; include specific details only in telemetry (not returned to user). |
| Developer docs become stale as tool evolves | Keep docs close to code; automate doc generation from code comments where possible; require doc updates in PR reviews. |
| Tool registration or schema changes break downstream consumers | Version the tool; deprecate old versions gradually; communicate breaking changes with lead time. |

### Phase 4 Checklist
- [ ] MCP tool schema finalized and registered with versioning.
- [ ] Error codes and messages standardized; suggestions provided for each.
- [ ] Developer docs complete: README, USAGE, SECURITY, TROUBLESHOOTING, EXAMPLES, FAQ.
- [ ] Example JSON requests/responses provided.
- [ ] Interactive testing script provided for developers.

### Phase 4 Checkpoints with Tests

**Unit Tests**
1. `test_sql_tool_schema_valid()`: Tool schema is valid JSON Schema.
2. `test_sql_tool_error_codes_documented()`: All error codes have defined messages and suggestions.

**Integration Tests**
3. `test_sql_tool_invocation_success()`: Tool invoked with valid question; returns success result.
4. `test_sql_tool_invocation_validation_failure()`: Tool invoked with question leading to validation failure; returns error with suggestion.
5. `test_sql_tool_invocation_rls_denial()`: Tool invoked by user without access; returns rls_denied error.
6.  `test_sql_tool_invocation_timeout()`: Tool invoked with slow query; returns timeout error.

**Manual Tests**
7. Developer walkthrough: Follow docs/EXAMPLES.md; walk through 3+ worked examples; verify tool behavior matches expectations.
8. Error message clarity: Review error messages for clarity and helpfulness (conducted by non-author).

**Approval Gate**: Developer docs reviewed by tech writer or domain expert; tool schema approved by API design lead; examples verified by a developer not involved in implementation.

---

## Phase 5: Hardening, Schema Governance, and Monitoring

### Objectives
1. Automate schema governance and allowlist validation.
2. Optimize performance with indices and materialized views.
3.  Implement continuous monitoring for data isolation and query health.

### Key Tasks

#### 5.1 Schema Governance and Automation
- **Action**: Implement automated schema snapshot and allowlist validation.
  - **Schema snapshot generation in CI**:
    - On each migration commit, run schema snapshot generator.
    - Capture current schema (views, columns, FK) in version-controlled file (e.g., `docs/schema-snapshots/schema_<date>.json`).
    - Git diff on snapshots; require code review of schema changes.
    - Add GitHub action: on migration merge, generate snapshot and auto-commit (or require manual approval).
  - **Allowlist validation in CI**:
    - On each allowlist change (e.g., `libs/vizu_sql_factory/config/allowlist.json`), validate:
      - All referenced views exist in current schema.
      - All referenced columns exist in those views.
      - No typos or orphaned entries.
      - Test that allowlist filtering works as expected (unit test).
    - Add GitHub action to validate allowlist on every commit.
  - **Audit trail**:
    - Track allowlist changes in git history (via commits).
    - Log schema changes and approval.
    - Generate periodic allowlist audit reports (e.g., monthly).
- **Deliverable**:
  - GitHub action: `. github/workflows/validate-schema-and-allowlist.yml`.
  - Schema snapshot generator enhancement: `libs/vizu_sql_factory/schema_snapshot. py` (add snapshot diffing).
  - Allowlist validator: `libs/vizu_sql_factory/allowlist_validator.py` with validation logic.
  - Example schema snapshot file: `docs/schema-snapshots/schema_2025-12-08.json`.

#### 5. 2 Performance Optimization
- **Action**: Identify and optimize performance hotspots.
  - **Monitoring**:
    - From Phase 3, identify slow queries (queries taking >1s or returning many rows).
    - Aggregate execution metrics per view (min, max, avg query time).
  - **Index recommendations**:
    - Analyze slow queries; recommend indices on:
      - WHERE clause columns (especially client_id, tenant filters).
      - JOIN predicates.
      - ORDER BY columns.
    - Document index recommendations in `docs/performance/index-recommendations.md`.
  - **Materialized views**:
    - For heavily-used aggregations or joins, propose materialized views.
    - Example: pre-compute monthly order counts per tenant.
    - Document refresh strategy (on-demand or scheduled).
  - **Implementation**:
    - Add indices via migrations in `supabase/migrations/`.
    - Measure impact (query time before/after).
    - Document in migration comments.
  - **Load testing**:
    - Create realistic query workload (e.g., 100 concurrent users, typical query mix).
    - Run against production-like schema.
    - Measure latency, throughput, resource usage.
    - Set performance baselines and SLOs (e.g., p95 latency <2s).
- **Deliverable**:
  - Performance monitoring added to Phase 3 observability (latency histograms per view).
  - Index recommendations documented.
  - Load testing script: `tests/performance/load_test. py`.
  - Performance baseline report: `docs/performance/baseline. md`.

#### 5.3 Continuous Monitoring for Data Isolation and Query Health
- **Action**: Build dashboards and alerts for operational health.
  - **Data isolation monitoring**:
    - Alert if RLS denial rate spikes (e.g., >1% of queries denied unexpectedly).
    - Alert if cross-tenant leakage is detected (manual audit weekly; automated checks if possible).
    - Validate that queries executed always include tenant predicate (via telemetry analysis).
  - **Query health**:
    - Track query success rate per tenant/role.
    - Alert if validation failure rate increases (may indicate schema or allowlist misconfiguration).
    - Alert if timeout rate increases (may indicate performance regression).
    - Track LLM hallucination rate (queries generating disallowed tables).
  - **Allowlist drift**:
    - Alert if schema changes without corresponding allowlist update.
    - Periodic (weekly) audit: compare current schema against allowlist; report gaps.
  - **Observability dashboard** (e.g., Grafana):
    - Query success rate over time.
    - Latency distribution (p50, p95, p99).
    - Error rate by error code.
    - RLS denial rate.
    - Validation pass rate.
    - LLM model performance (tokens, cost per query).
    - Queries per tenant/role (trending).
  - **Alerting** (e.g., PagerDuty):
    - Critical: Cross-tenant leakage, RLS denial spike, all queries failing.
    - Warning: Timeout rate >5%, validation failure rate >10%, schema drift.
  - **Audit logs**:
    - Retain telemetry for 90 days; periodic export for compliance.
    - Include query question (hash), SQL, result count, tenant, role, outcome.
    - Enable forensics for security incidents.
- **Deliverable**:
  - Monitoring queries/dashboards (Grafana JSON or SQL).
  - Alert rules (PagerDuty or equivalent).
  - Audit log setup (export, retention policy).
  - Documentation: `docs/operations/monitoring. md`, `docs/operations/alerts.md`.

#### 5.4 Regular Audit and Improvement Process
- **Action**: Establish operational cadence for review and hardening.
  - **Weekly**:
    - Review error logs; identify new error patterns or allowlist misconfigurations.
    - Check RLS denial logs for legitimacy.
  - **Monthly**:
    - Full schema vs.  allowlist audit (automated report).
    - Performance review: slow query analysis, index effectiveness.
    - LLM quality review: sample generated SQL; measure hallucination and constraint adherence.
    - Cost review (LLM calls, Supabase quota usage).
  - **Quarterly**:
    - Security review: review validation logic, test cross-tenant isolation.
    - Capacity planning: growth in query volume, data size; adjust limits and indices.
    - Documentation review: ensure SECURITY.md, TROUBLESHOOTING.md match reality.
  - **Runbook**:
    - Create operational runbook: `docs/operations/runbook. md` with common troubleshooting, escalation procedures, and emergency shutdown steps.
- **Deliverable**:
  - Audit checklist: `docs/operations/audit-checklist.md`.
  - Runbook: `docs/operations/runbook.md`.
  - Scheduled review process (calendar invites, RACI matrix).

### Implementation Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Allowlist validation in CI is strict and blocks legitimate schema changes | Design validator to warn before failing; allow override with explicit approval. |
| Performance optimization introduces regressions or instability | Test indices and materialized views thoroughly; measure before/after; have rollback plan. |
| Alert fatigue: too many alerts; on-call burnout | Tune alert thresholds carefully; start conservative; adjust based on alert noise. |
| Audit logs grow unbounded; storage/cost explosion | Implement log rotation and archival; export to cold storage (S3, Glacier) for compliance. |

### Phase 5 Checklist
- [ ] Schema snapshot generation and validation automated in CI.
- [ ] Allowlist validation automated; enforced on every commit.
- [ ] Performance monitoring integrated; slow query identification and recommendations.
- [ ] Load testing baseline established; SLOs defined.
- [ ] Monitoring dashboard (Grafana) and alerting