# Text-to-SQL Tool — Security Model

## Overview

The Text-to-SQL tool is designed with **security first**. Every query is validated against a multi-layered security model to prevent unauthorized data access, runaway queries, and cross-tenant data leakage.

## Security Layers

### 1. Authentication & Authorization

**JWT-based identity:**
- Every invocation includes a user JWT with tenant context
- `tenant_id` is extracted from the JWT (not from user input)
- `role` determines the user's permissions and schema access

**Role-based access control (RBAC):**
- Different roles have different views, columns, and row limits
- **Viewer** — Read-only, basic views, 100 rows max
- **Analyst** — Read-only, core views, 10,000 rows max
- **Admin** — Read-only, all views, 100,000 rows max

### 2. Row-Level Security (RLS)

**Database-level enforcement:**
- Postgres RLS policies ensure users only see their tenant's data
- Even if SQL is valid, RLS prevents cross-tenant access
- Every query is executed in the context of the authenticated user's JWT

**Multi-tenant isolation:**
- All tables have a `client_id` column (or equivalent)
- RLS policies automatically filter by `client_id` matching the user's tenant
- Queries that don't include the tenant filter are rewritten to add it

**Example:** A user from Acme Corp (tenant_id: `acme-123`) querying customers will only see rows where `client_id = 'acme-123'`, even if the SQL doesn't explicitly include that filter.

### 3. View Allowlist

**What it is:**
- A configuration file listing approved views and columns for each role
- Only these views/columns can be used in generated queries

**How it works:**
1. User asks a question → LLM generates SQL
2. SQL validation checks if all tables/columns are in the allowlist
3. If not, query is rejected with `validation_failed` error
4. User is told which views are available for their role

**Example allowlist:**
```json
{
  "viewer": {
    "views": ["customers", "orders", "products"],
    "columns": {
      "customers": ["id", "name", "email", "created_at"],
      "orders": ["id", "customer_id", "total", "status", "created_at"]
    }
  },
  "analyst": {
    "views": ["customers", "orders", "products", "transactions", "payments"],
    "columns": {
      // ... more columns ...
    }
  }
}
```

### 4. Query Validation & Rewriting

**Validation checks:**
1. **Schema validation** — All tables and columns exist
2. **Allowlist validation** — All objects are in the role's allowlist
3. **Constraint validation** — Query includes required security filters (e.g., `client_id`)
4. **Syntax validation** — SQL is well-formed and safe

**Safe query rewriting:**
- If a query lacks required security filters, the system adds them
- Example: User asks "Show customers" → Rewritten to "SELECT * FROM customers WHERE client_id = 'acme-123'"

**Forbidden operations:**
- No INSERT, UPDATE, DELETE, DROP, CREATE, or ALTER statements
- No stored procedure calls or dynamic SQL execution
- No union queries (can bypass row filtering)
- No temporary tables or CTEs that escape filtering scope

### 5. Result Sanitization

**PII masking:**
- Sensitive fields (SSN, credit card) may be masked in results
- Full PII is never returned to non-admin users

**Size limits:**
- Role-based row limits enforced in database and application
- Results are paginated if they exceed the limit
- Users are warned if results are truncated (`caveats` field)

**Cell size limits:**
- Large text fields are truncated to prevent memory exhaustion
- Binary/blob fields are not returned

### 6. Execution Safety

**Timeout protection:**
- All queries have a 30-second execution timeout
- Queries that take longer are killed and return `execution_timeout` error

**Resource limits:**
- Max connections enforced by database
- Query complexity monitoring (query cost estimation)
- Concurrent query throttling per tenant

**Audit logging:**
- All queries are logged (question, SQL, tenant, result count, execution time, outcome)
- Logs include telemetry ID for correlation
- Logs are retained for compliance and incident investigation

## What Data is Visible by Role?

### Viewer Role

**Typical schema access:**
- `customers` (name, email, created_at, status)
- `orders` (order ID, customer, total, status, date)
- `products` (product ID, name, price, category)

**Use cases:**
- Executive dashboards
- Basic reporting
- Read-only data exploration

**Constraints:**
- Max 100 rows per query
- No access to costs, payments, or internal tables

### Analyst Role

**Typical schema access:**
- All viewer tables +
- `transactions` (detailed financial data)
- `payments` (payment methods, history)
- `invoices` (billing records)
- `users` (user accounts and roles)

**Use cases:**
- Ad-hoc analytics
- Detailed financial reporting
- Customer analysis

**Constraints:**
- Max 10,000 rows per query
- No access to internal cost tables or salaries

### Admin Role

**Typical schema access:**
- All tables and views

**Use cases:**
- System administration
- Full data audits
- Large-scale exports for external compliance

**Constraints:**
- Max 100,000 rows per query
- All operations logged and auditable

## How Cross-Tenant Leakage is Prevented

1. **Authentication** — User identity and tenant verified via JWT
2. **RLS** — Database policies enforce tenant isolation at the row level
3. **Query rewriting** — Missing tenant filters are added automatically
4. **Allowlist** — Only approved views are accessible (no system tables)
5. **Audit** — Every query is logged with tenant context for forensics

**Scenario:** Attacker tries to query another tenant's data.

```sql
-- Attacker tries: SELECT * FROM customers WHERE tenant_id = 'victim-456'
-- System rewrites to: SELECT * FROM customers WHERE tenant_id = 'victim-456' AND client_id = 'attacker-123'
-- Result: No rows (RLS policy blocks access since client_id != tenant_id)
```

## How Runaway Queries are Prevented

1. **Timeout** — 30-second limit kills slow queries
2. **Row limits** — Role-based limits (100/10K/100K rows)
3. **Query rewriting** — LIMIT clauses added automatically
4. **Resource monitoring** — Database alerts if CPU/memory usage spikes

## Security Responsibilities

### The System's Role
- Authenticate users via JWT
- Enforce RLS at the database level
- Validate queries against allowlists
- Rewrite queries to add security filters
- Sanitize results before returning

### Your Role (Admin/Operator)
- Keep allowlist up-to-date as schema evolves
- Review and approve schema changes
- Monitor audit logs for suspicious activity
- Define appropriate row limits per role
- Respond to security incidents

## Transparency

All security information is available to users:
- **Audit logs** — Available for compliance and investigation
- **Error messages** — Tell users why queries were rejected (with suggestions)
- **Telemetry** — Every query has a unique ID for correlation and debugging

## Compliance & Standards

The tool adheres to:
- **RBAC** — Role-based access control (industry standard)
- **RLS** — Row-level security (database best practice)
- **PII protection** — Data masking for sensitive fields
- **Audit trails** — Comprehensive logging for compliance (SOC 2, HIPAA, etc.)
- **Multi-tenancy** — Complete tenant isolation

## FAQs

### Q: Can I bypass the allowlist?
**A:** No. The allowlist is enforced at the database level by RLS policies. Even if the LLM generates SQL that references forbidden tables, it will be rejected before execution.

### Q: What if a query bypasses RLS?
**A:** This would be a critical security bug. Report it immediately to security@vizu.io with:
- Telemetry ID of the query
- User's tenant and role
- Result demonstrating the leak

### Q: Can admins see other tenants' data?
**A:** No. Admin role has access to more views/columns, but RLS still enforces tenant isolation. Admins can only see their own tenant's data (unless explicitly running as a different tenant for support purposes, which is audited).

### Q: How often are allowlists reviewed?
**A:** Allowlists should be reviewed:
- Monthly (standard audit)
- When schema changes
- When new roles are added
- Annually (full compliance audit)

See [Operations Guide](../operations/audit-checklist.md) for details.

### Q: What happens to old query logs?
**A:** Logs are retained for:
- 30 days: Hot storage (fast access for incident response)
- 90 days: Archive storage (cold, cheaper)
- Deleted after 90 days (unless longer retention required for compliance)

Custom retention policies can be configured per tenant.

## Support & Incident Response

### Reporting Security Issues
- **Non-critical issues** — Open a GitHub issue with `[SECURITY]` label
- **Critical issues** — Email security@vizu.io immediately
- **Include** — Telemetry ID, reproduction steps, impact assessment

### Incident Investigation
1. Retrieve audit logs using telemetry ID
2. Check RLS policies were in effect during the query
3. Verify tenant_id in JWT matches query results
4. Check for any allowlist misconfigurations
5. Review application logs for any bypasses

For detailed incident response, see [Operations Guide](../operations/runbook.md).
