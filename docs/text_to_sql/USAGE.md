# Text-to-SQL Tool — Usage Guide

## Tool Signature

### Tool Name
`query_database_text_to_sql`

### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `question` | string | Yes | Natural language question (5-500 chars). Example: "How many orders in the last 7 days?" |
| `tenant_id` | string (UUID) | Yes | Your organization identifier. Usually extracted from JWT at runtime. |
| `role` | string | Yes | Your role: `viewer`, `analyst`, or `admin`. Determines schema access and row limits. |
| `optional_constraints` | object | No | Query constraints (date_range, max_rows, etc.). See examples below. |

#### `optional_constraints` Sub-fields

| Field | Type | Allowed Values | Description |
|-------|------|----------------|-------------|
| `date_range` | string | `last_7_days`, `last_30_days`, `last_90_days`, `year_to_date` | Narrows time scope |
| `max_rows` | integer | 1–100,000 (role-dependent) | Override default row limit |
| `customer_segment` | string | Custom | Domain-specific filter (e.g., "premium", "active") |

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | True if query succeeded; false if failed |
| `sql` | string or null | The SQL query executed (or null if validation/generation failed) |
| `rows` | array | Query results (list of objects) |
| `columns` | array | Column metadata: `[{"name": "...", "type": "..."}]` |
| `caveats` | array | Execution notes (e.g., "Result limited to 100 rows") |
| `error` | object or null | Structured error (null if successful) with `code`, `message`, `suggestion` |
| `telemetry_id` | string | UUID for tracing logs and debugging |
| `execution_time_ms` | number | Query execution time in milliseconds |

## Common Use Cases

### 1. Simple Aggregation

**Question:** "Count orders by status"

**Invocation:**
```json
{
  "question": "Count orders by status",
  "tenant_id": "acme-corp-123",
  "role": "analyst"
}
```

**Response:**
```json
{
  "success": true,
  "sql": "SELECT status, COUNT(*) as count FROM public.orders WHERE client_id = 'acme-corp-123' GROUP BY status",
  "rows": [
    {"status": "pending", "count": 15},
    {"status": "completed", "count": 342},
    {"status": "canceled", "count": 8}
  ],
  "columns": [
    {"name": "status", "type": "text"},
    {"name": "count", "type": "integer"}
  ],
  "caveats": [],
  "error": null,
  "telemetry_id": "123e4567-e89b-12d3-a456-426614174000",
  "execution_time_ms": 150.2
}
```

### 2. Join and Filtering

**Question:** "Show me customer names and their total spending in the last 30 days"

**Invocation:**
```json
{
  "question": "Show me customer names and their total spending in the last 30 days",
  "tenant_id": "acme-corp-123",
  "role": "analyst",
  "optional_constraints": {
    "date_range": "last_30_days",
    "max_rows": 50
  }
}
```

**Response:**
```json
{
  "success": true,
  "sql": "SELECT c.name, SUM(o.total) as total_spending FROM public.customers c JOIN public.orders o ON c.id = o.customer_id WHERE c.client_id = 'acme-corp-123' AND o.client_id = 'acme-corp-123' AND o.created_at >= NOW() - INTERVAL '30 days' GROUP BY c.id, c.name ORDER BY total_spending DESC LIMIT 50",
  "rows": [
    {"name": "Acme Inc", "total_spending": 15000.50},
    {"name": "TechCorp", "total_spending": 12340.00},
    {"name": "Global Ltd", "total_spending": 8900.75}
  ],
  "columns": [
    {"name": "name", "type": "text"},
    {"name": "total_spending", "type": "numeric"}
  ],
  "caveats": ["Result limited to 50 rows (role limit: 10000)"],
  "error": null,
  "telemetry_id": "234f5678-e89b-12d3-a456-426614174001",
  "execution_time_ms": 287.5
}
```

### 3. Time-Series Data

**Question:** "Show daily order counts for the last 7 days"

**Invocation:**
```json
{
  "question": "Show daily order counts for the last 7 days",
  "tenant_id": "acme-corp-123",
  "role": "analyst",
  "optional_constraints": {
    "date_range": "last_7_days"
  }
}
```

**Response:**
```json
{
  "success": true,
  "sql": "SELECT DATE(created_at) as date, COUNT(*) as count FROM public.orders WHERE client_id = 'acme-corp-123' AND created_at >= NOW() - INTERVAL '7 days' GROUP BY DATE(created_at) ORDER BY date DESC",
  "rows": [
    {"date": "2025-01-15", "count": 45},
    {"date": "2025-01-14", "count": 38},
    {"date": "2025-01-13", "count": 52},
    {"date": "2025-01-12", "count": 41},
    {"date": "2025-01-11", "count": 49},
    {"date": "2025-01-10", "count": 55},
    {"date": "2025-01-09", "count": 39}
  ],
  "columns": [
    {"name": "date", "type": "date"},
    {"name": "count", "type": "integer"}
  ],
  "caveats": [],
  "error": null,
  "telemetry_id": "345f6789-e89b-12d3-a456-426614174002",
  "execution_time_ms": 198.1
}
```

### 4. Error Scenario: Validation Failure

**Question:** "Show me all transactions from the billing database"

**Invocation:**
```json
{
  "question": "Show me all transactions from the billing database",
  "tenant_id": "acme-corp-123",
  "role": "viewer"
}
```

**Response (Error):**
```json
{
  "success": false,
  "sql": null,
  "rows": [],
  "columns": [],
  "caveats": [],
  "error": {
    "code": "validation_failed",
    "message": "The generated SQL does not meet safety constraints. Query references a disallowed table (billing_transactions).",
    "suggestion": "Available tables for viewer role: customers, orders, products. Try asking about those instead, or contact your administrator for access."
  },
  "telemetry_id": "456f7890-e89b-12d3-a456-426614174003",
  "execution_time_ms": 125.0
}
```

### 5. Error Scenario: Timeout

**Question:** "Show me all transactions ever"

**Invocation:**
```json
{
  "question": "Show me all transactions ever",
  "tenant_id": "acme-corp-123",
  "role": "analyst"
}
```

**Response (Error):**
```json
{
  "success": false,
  "sql": "SELECT * FROM public.transactions WHERE client_id = 'acme-corp-123'",
  "rows": [],
  "columns": [],
  "caveats": [],
  "error": {
    "code": "execution_timeout",
    "message": "Query execution timed out after 30 seconds. The query is requesting too much data or performing too many complex operations.",
    "suggestion": "Try narrowing the query scope: 1. Specify a date range ('last 7 days' instead of 'all time'). 2. Reduce rows ('top 10' instead of all). 3. Ask about specific metrics. 4. Contact support for very large datasets."
  },
  "telemetry_id": "567f8901-e89b-12d3-a456-426614174004",
  "execution_time_ms": 30000.0
}
```

## Example JSON Files

See the `examples/` directory for complete request/response pairs:
- `example_aggregation_request.json` / `response.json`
- `example_join_request.json` / `response.json`
- `example_timeseries_request.json` / `response.json`
- `example_error_validation_request.json` / `response.json`
- `example_error_timeout_request.json` / `response.json`

## Tips for Best Results

1. **Be specific** — Include the data you want and any relevant filters
   - ✓ Good: "Top 10 products by revenue in the last 30 days"
   - ✗ Vague: "Show me products"

2. **Use domain language** — Refer to actual table/column names if you know them
   - ✓ Good: "Customer revenue this year"
   - ✗ Vague: "Money stuff"

3. **Narrow the scope** — Use date ranges, specific metrics, or top-N results
   - ✓ Good: "Last 7 days, top 5"
   - ✗ Risky: "All data"

4. **Try rephrasing** — If a question fails, rephrase more specifically
   - First attempt: "Count things"
   - Rephrased: "How many active customers do we have?"

## Role-Based Access

### Viewer
- **Max rows per query:** 100
- **Available views:** Basic reporting views (customers, orders, products)
- **Use case:** Dashboards, executive summaries

### Analyst
- **Max rows per query:** 10,000
- **Available views:** Core views + fact tables (transactions, payments, invoices)
- **Use case:** Detailed analysis, reporting, ad-hoc queries

### Admin
- **Max rows per query:** 100,000
- **Available views:** All tables and views
- **Use case:** System administration, large exports

## Troubleshooting

For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Common issues:
- **"llm_unable"** — Try rephrasing your question more specifically
- **"validation_failed"** — Check available tables/columns for your role
- **"execution_timeout"** — Narrow the scope with date ranges or row limits
- **"rls_denied"** — Verify you're asking about your organization's data
