# Text-to-SQL Tool

Query your database using natural language questions.

## Overview

The Text-to-SQL tool (`query_database_text_to_sql`) translates natural language questions into secure SQL queries. The tool:

1. **Understands your question** — Uses a large language model (LLM) to interpret what you're asking
2. **Validates safety** — Ensures the generated SQL complies with security constraints (RLS, allowlists)
3. **Executes securely** — Runs queries with row-level security (RLS) to prevent cross-tenant data leakage
4. **Returns results** — Provides results with column metadata and execution details

### Key Properties

- **Multi-tenant isolation** — Each tenant sees only their own data via row-level security (RLS)
- **Role-based access** — Different roles (viewer, analyst, admin) have different query limits and schema access
- **Safety by default** — All queries are validated against an allowlist of safe views and columns
- **View-only reads** — Queries can only read data; no writes or deletes are allowed
- **Result limits** — Role-based limits prevent runaway queries that consume excessive resources

## Quick Start

### Example: Simple Question

**Question:** "How many customers signed up last month?"

**Tool invocation:**
```json
{
  "question": "How many customers signed up last month?",
  "tenant_id": "acme-corp-123",
  "role": "analyst"
}
```

**Response:**
```json
{
  "success": true,
  "sql": "SELECT COUNT(*) as count FROM public.customers WHERE client_id = 'acme-corp-123' AND created_at >= NOW() - INTERVAL '30 days'",
  "rows": [{"count": 42}],
  "columns": [{"name": "count", "type": "integer"}],
  "caveats": [],
  "error": null,
  "telemetry_id": "a1b2c3d4-e5f6-4a5b-8c9d-e0f1a2b3c4d5",
  "execution_time_ms": 245.3
}
```

## Understanding Responses

### Success Response

When a query succeeds, you receive:

- **`success`** — Always `true` for successful queries
- **`sql`** — The SQL query that was executed (may be rewritten for safety)
- **`rows`** — Query results as a list of objects
- **`columns`** — Column metadata: name and type
- **`caveats`** — Notes about the result (e.g., "Result limited to 100 rows")
- **`execution_time_ms`** — How long the query took to run (in milliseconds)

### Error Response

When a query fails, you receive an error object with:

- **`success`** — Always `false` for failed queries
- **`error.code`** — Machine-readable error code (see [Error Codes](#error-codes))
- **`error.message`** — Human-readable explanation of what went wrong
- **`error.suggestion`** — Actionable hints for fixing the problem

Example error:
```json
{
  "success": false,
  "sql": null,
  "rows": [],
  "columns": [],
  "error": {
    "code": "validation_failed",
    "message": "The generated SQL does not meet safety constraints. Query references a disallowed view (base_customers_table).",
    "suggestion": "Available views for your role are: customers, orders, products. Try asking about those instead."
  },
  "telemetry_id": "b2c3d4e5-f6a7-5b6c-9d0e-f1a2b3c4d5e6",
  "execution_time_ms": 125.0
}
```

## Error Codes

### `llm_unable`

The AI language model was unable to formulate a query.

**Cause:** Your question is outside the scope of available data, too ambiguous, or uses unfamiliar terminology.

**Example:** "Explain quantum mechanics" (not a data question)

**How to fix:**
- Rephrase more specifically, including the data you want and any filters (e.g., date ranges)
- Include metric names or table names if you know them
- Ask about specific business entities (customers, orders, products)

### `validation_failed`

The generated SQL does not meet safety constraints.

**Cause:** The query references restricted views/columns, lacks required security filters, or violates other policies.

**Example:** A viewer-role user asking about internal cost data

**How to fix:**
- Review the suggestion for available views/columns for your role
- Ask about the data you're allowed to access
- Contact your administrator if you need access to additional data

### `rls_denied`

Row-level security denied access to the requested data.

**Cause:** Your security profile (determined by RLS policies) prevents you from accessing this data.

**Example:** Trying to access another tenant's data

**How to fix:**
- Confirm you're asking about your own organization's data
- Contact your administrator if you believe this is incorrect

### `execution_timeout`

Query execution timed out after 30 seconds.

**Cause:** The query is requesting too much data or performing complex operations.

**Example:** Asking for "all transactions ever" without date filtering

**How to fix:**
- Narrow the scope: specify a date range (e.g., "last 7 days" not "all time")
- Ask for top-N results (e.g., "top 10 customers by revenue" not "all customers")
- Ask about fewer metrics or join fewer tables
- Contact support for very large dataset exports

### `schema_unavailable`

Schema metadata is temporarily unavailable.

**Cause:** The system cannot access the database schema right now (rare).

**How to fix:**
- Try again in a moment
- If the issue persists, contact support with the telemetry ID

### `internal_error`

An unexpected internal error occurred.

**Cause:** Server-side issue, not a problem with your query.

**How to fix:**
- Contact support with the telemetry ID so we can investigate

## Security

### What You See

Your role determines what views and columns you can access:

- **Viewer** — Read-only access to basic reporting views; limited to 100 rows per query
- **Analyst** — Access to core views and fact tables; limited to 10,000 rows per query
- **Admin** — Access to all views and tables; limited to 100,000 rows per query

### How Data is Protected

1. **Row-Level Security (RLS)** — Database-level policies ensure you only see your tenant's data
2. **Allowlist** — Your role only has access to specific approved views and columns
3. **Mandatory filters** — Queries must include security filters (e.g., client_id for multi-tenant isolation)
4. **Query rewriting** — The system may rewrite your query to add security filters
5. **View-only access** — All queries are read-only; no writes or deletes

## Next Steps

- See [USAGE.md](USAGE.md) for tool parameter details and more examples
- See [EXAMPLES.md](EXAMPLES.md) for worked examples covering common use cases
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions
- See [FAQ.md](FAQ.md) for frequently asked questions
- See [SECURITY.md](SECURITY.md) for details about the security model

## Support

For issues or questions:
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and [FAQ.md](FAQ.md) first
2. Provide the telemetry ID from the error response when contacting support
3. Include your question and any error messages
