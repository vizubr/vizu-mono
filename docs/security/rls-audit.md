# RLS Audit Report: Text-to-SQL Foundation

**Date**: 2025-01-01
**Status**: Initial Audit (Phase 0.1)
**Scope**: All tables in `public` schema relevant to text-to-SQL safe execution.

---

## Executive Summary

The current Vizu schema has **multi-tenant isolation** built on the `cliente_vizu` table (tenant root), with all operational tables (cliente_final, configuracao_negocio, credencial_servico_externo, fonte_de_dados) linked via foreign key `cliente_vizu_id`.

**RLS Status**: Partially enabled (cliente_vizu and configuracao_negocio have basic service-role + authenticated policies). **Missing**: tenant-filtered RLS on operational tables (cliente_final, credencial_servico_externo, fonte_de_dados).

**No database views currently exist**; all text-to-SQL queries will operate directly on tables.

---

## Current Schema Structure

### Core Tables

#### 1. `cliente_vizu` (Tenant Root)
- **Purpose**: Tenant identity and configuration.
- **Columns**:
  - `id` (uuid, PK, default gen_random_uuid())
  - `nome_empresa` (varchar 255, NOT NULL)
  - `tipo_cliente` (enum: B2B, B2C, EXTERNO)
  - `tier` (enum: FREE, BASIC, PREMIUM, ENTERPRISE, SME)
  - `api_key` (varchar 255, unique, default gen_random_uuid())
  - `horario_funcionamento` (jsonb)
  - `prompt_base` (text)
  - `ferramenta_rag_habilitada` (boolean)
  - `ferramenta_sql_habilitada` (boolean)
  - `ferramenta_agendamento_habilitada` (boolean)
  - `collection_rag` (text)
- **RLS Status**: ✅ **Enabled**
  - Policy: `allow_service_role_all_cliente_vizu` (service role can read/write all)
  - Policy: `allow_authenticated_select_cliente_vizu` (authenticated users can select)
  - **Gap**: No tenant-filtering for authenticated users (can see other tenants).
- **Index**: `ix_cliente_vizu_api_key` (unique on api_key)

#### 2. `cliente_final` (End-User/Customer Records)
- **Purpose**: Customer records within each tenant.
- **Columns**:
  - `id` (int, PK, auto-increment)
  - `id_externo` (varchar, external reference)
  - `nome` (varchar 255)
  - `metadados` (json)
  - `cliente_vizu_id` (uuid, FK to cliente_vizu)
- **RLS Status**: ❌ **NOT Enabled**
  - **Gap**: Any authenticated user can read all customers across tenants.
- **Index**: `ix_cliente_final_id_externo` (for external ID lookups)

#### 3. `configuracao_negocio` (Business Configuration)
- **Purpose**: Tenant feature toggles and settings (merged into cliente_vizu in recent migration).
- **Columns**:
  - `id` (int, PK, auto-increment)
  - `horario_funcionamento` (json)
  - `prompt_base` (varchar)
  - `ferramenta_rag_habilitada` (boolean, default false)
  - `ferramenta_sql_habilitada` (boolean, default false)
  - `ferramenta_agendamento_habilitada` (boolean, default false)
  - `cliente_vizu_id` (uuid, FK to cliente_vizu)
- **RLS Status**: ✅ **Enabled**
  - Policy: `allow_service_role_all_configuracao` (service role)
  - Policy: `allow_authenticated_select_configuracao` (authenticated)
  - **Gap**: No tenant-filtering (can see other tenants' configurations).
- **Index**: `ix_configuracao_negocio_cliente_vizu_id` (unique on tenant)

#### 4. `credencial_servico_externo` (External Service Credentials)
- **Purpose**: Store API keys/credentials for external integrations (Twilio, OAuth, etc.).
- **Columns**:
  - `id` (int, PK, auto-increment)
  - `nome_servico` (varchar, e.g., "twilio", "google_oauth")
  - `cliente_vizu_id` (uuid, FK to cliente_vizu)
- **RLS Status**: ❌ **NOT Enabled**
  - **Gap**: Highly sensitive; credentials can be exposed to other tenants.
  - **Recommendation**: Critical RLS policy required; consider encryption.

#### 5. `fonte_de_dados` (Data Source / RAG Document Ingestion)
- **Purpose**: Track data sources (files, URLs) for RAG/knowledge base per tenant.
- **Columns**:
  - `id` (int, PK, auto-increment)
  - `tipo_fonte` (enum: URL)
  - `caminho` (varchar, e.g., file path or URL)
  - `cliente_vizu_id` (uuid, FK to cliente_vizu)
- **RLS Status**: ❌ **NOT Enabled**
  - **Gap**: No RLS prevents cross-tenant data source access.

### Legacy Table (Deprecated)
- **`alembic_version`**: Migration tracker. No RLS needed.

---

## RLS Policy Gaps & Recommendations

### Critical Gaps (Must Fix Before Phase 1)

| Table | Current RLS | Gap | Risk | Recommended Policy |
|-------|-------------|-----|------|-------------------|
| `cliente_vizu` | Partial | No tenant-filtering for authenticated users | Medium | `SELECT USING (id = current_user_id OR is_admin)` — requires JWT claim extraction |
| `cliente_final` | ❌ None | Can read all customers across tenants | **High** | `SELECT/INSERT/UPDATE USING (cliente_vizu_id = current_tenant_id)` |
| `configuracao_negocio` | Partial | No tenant-filtering | Medium | `SELECT USING (cliente_vizu_id = current_tenant_id)` |
| `credencial_servico_externo` | ❌ None | Can expose credentials across tenants | **Critical** | `SELECT/INSERT/UPDATE USING (cliente_vizu_id = current_tenant_id)`; consider encryption at rest |
| `fonte_de_dados` | ❌ None | Can access other tenants' data sources | High | `SELECT/INSERT/UPDATE USING (cliente_vizu_id = current_tenant_id)` |

### Implementation Strategy

**Phase 0 Deliverable**: RLS policy templates ready for migration (Phase 2).

**Phase 0.5 Task**: Supabase client JWT extraction must support `current_tenant_id` via JWT claim:
- Assume JWT contains `sub` (user ID) and `tenant_id` (or organization ID) claims.
- Create Supabase function `current_tenant_id()` that extracts tenant_id from JWT claims.

**Example RLS Policy Template** (to be added in Phase 2 migration):
```sql
-- For cliente_final table
CREATE POLICY "tenant_isolation_cliente_final" ON cliente_final
  FOR SELECT USING (cliente_vizu_id = (auth.jwt() ->> 'tenant_id')::uuid)
  WITH CHECK (cliente_vizu_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- For credencial_servico_externo table
CREATE POLICY "tenant_isolation_credentials" ON credencial_servico_externo
  FOR ALL USING (cliente_vizu_id = (auth.jwt() ->> 'tenant_id')::uuid)
  WITH CHECK (cliente_vizu_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- For fonte_de_dados table
CREATE POLICY "tenant_isolation_data_sources" ON fonte_de_dados
  FOR ALL USING (cliente_vizu_id = (auth.jwt() ->> 'tenant_id')::uuid)
  WITH CHECK (cliente_vizu_id = (auth.jwt() ->> 'tenant_id')::uuid);
```

---

## Database Views (None Exist Yet)

### Planned Views for Text-to-SQL (Phase 1)

To support safe read-only queries, we will create role-specific views:

1. **`customers_view`** (analyst role)
   - Purpose: Customer/cliente_final data (name, ID, metadata).
   - Columns: `id`, `id_externo`, `nome`, `created_at` (if available), RLS-filtered by tenant_id.
   - Source: `cliente_final`.

2. **`data_sources_summary_view`** (analyst role)
   - Purpose: List of data sources used for RAG (read-only).
   - Columns: `id`, `tipo_fonte`, `caminho`, `created_at`.
   - Source: `fonte_de_dados`, filtered by tenant_id.

3. **`service_credentials_list_view`** (admin role only)
   - Purpose: List external service integrations (no actual secrets).
   - Columns: `id`, `nome_servico`, `is_active`.
   - Source: `credencial_servico_externo`, masked/no-secret version.

4. **`tenant_config_view`** (analyst role)
   - Purpose: Readable tenant configuration (hours, RAG setting, SQL enabled).
   - Columns: `horario_funcionamento`, `ferramenta_rag_habilitada`, `ferramenta_sql_habilitada`.
   - Source: `cliente_vizu` or `configuracao_negocio`.

---

## Authentication & JWT Claims Assumptions

For RLS and text-to-SQL to work securely:

1. **JWT Claims Required**:
   - `sub` (subject/user ID)
   - `tenant_id` (organization/client UUID)
   - `role` (e.g., "analyst", "viewer", "admin")
   - `exp` (expiration timestamp)

2. **Supabase PostgREST Integration**:
   - User requests include `Authorization: Bearer <JWT>` header.
   - Supabase automatically decodes JWT and makes claims available via `auth.jwt()` function.
   - RLS policies use `auth.jwt() ->> 'tenant_id'` to enforce tenant isolation.

3. **Service Role Bypass**:
   - Service role (internal API calls, batch jobs) bypasses RLS.
   - For internal tools (batch ingestion, admin tasks), use service-role token.
   - Never expose service-role token to clients.

---

## Audit Checklist & Next Steps

### ✅ Audit Findings
- [x] Enumerated all tables in `public` schema.
- [x] Documented current RLS policies on cliente_vizu and configuracao_negocio.
- [x] Identified critical RLS gaps on cliente_final, credencial_servico_externo, fonte_de_dados.
- [x] No database views exist yet (will be created in Phase 1/2).
- [x] JWT claims structure assumed (to be confirmed in Phase 0.5).

### 📋 Phase 0 Remaining Tasks
1. **Phase 0.2**: Design and freeze allowlist.json (which views/columns per role).
2. **Phase 0.3**: Build SchemaSnapshotGenerator (will introspect views once created).
3. **Phase 0.4**: Design SQL validator (stub implementation).
4. **Phase 0.5**: Wire Supabase client with JWT extraction and PostgREST pagination.
5. **Phase 0.6**: Register MCP tool skeleton.

### 🔐 Phase 2 Critical Task
- [ ] Create and deploy RLS policies for cliente_final, credencial_servico_externo, fonte_de_dados.
- [ ] Create database views (customers_view, data_sources_summary_view, etc.) with RLS inherited.
- [ ] Test RLS enforcement via PostgREST with test user JWTs.

---

## Security Recommendations Summary

| Priority | Item | Owner | Timeline |
|----------|------|-------|----------|
| **P0 (Critical)** | Add RLS to credencial_servico_externo (credential exposure) | Backend | Phase 2 |
| **P1 (High)** | Add RLS to cliente_final, fonte_de_dados | Backend | Phase 2 |
| **P1 (High)** | Encrypt secrets in credencial_servico_externo at rest | DB/Backend | Phase 2 |
| **P2 (Medium)** | Fix cliente_vizu RLS to filter by tenant for authenticated users | Backend | Phase 2 |
| **P2 (Medium)** | Create role-specific views for text-to-SQL queries | Backend | Phase 1/2 |
| **P3 (Low)** | Add audit logging for credential/data source access | Backend | Phase 3 |

---

## Sign-Off

**Auditor**: AI Code Agent
**Date**: 2025-01-01
**Status**: Ready for Phase 0.2 (allowlist design)
