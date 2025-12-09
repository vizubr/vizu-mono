# Text-to-SQL Tool — Troubleshooting Guide

## Common Issues and Solutions

### Issue: "llm_unable" Error

**Error message:**
```
The AI language model was unable to formulate a query. This may indicate the question is
outside the scope of available data or is too ambiguous.
```

**Causes:**
1. Question is unclear or uses unfamiliar terminology
2. Question is not about data (e.g., "explain quantum mechanics")
3. Question lacks specificity about what data you want

**Solutions:**

1. **Rephrase more specifically:**
   - ❌ Vague: "Show me data"
   - ✓ Specific: "How many active customers do we have?"

2. **Include relevant filters:**
   - ❌ Too broad: "Show all transactions"
   - ✓ Scoped: "Show me transactions from the last 30 days"

3. **Use business terminology:**
   - ❌ Technical: "Execute an aggregation on the fact table"
   - ✓ Business: "Total revenue by product category"

4. **Ask for specific metrics:**
   - ❌ Open-ended: "Tell me about orders"
   - ✓ Specific: "How many orders were placed yesterday? How much revenue?"

5. **Break into simpler questions:**
   - ❌ Complex: "Show me the top 10 customers by revenue, their segment, and their contact info"
   - ✓ Simpler: "Who are the top 10 customers by revenue?" (then ask about details separately)

**Still not working?** Contact support with:
- Telemetry ID
- Your question (exact wording)
- What you were trying to find

---

### Issue: "validation_failed" Error

**Error message:**
```
The generated SQL does not meet safety constraints. Query references a disallowed
table (base_customers_table). Available views for your role: customers, orders, products.
```

**Causes:**
1. You asked about tables/columns your role can't access
2. You mentioned system/internal tables
3. Question requires data you don't have permission to see

**Solutions:**

1. **Check available views for your role:**
   - **Viewer:** customers, orders, products
   - **Analyst:** + transactions, payments, invoices, users
   - **Admin:** all tables

2. **Rephrase using allowed views:**
   - ❌ Blocked: "Show me internal cost data"
   - ✓ Allowed: "Show me order totals and profit margins"

3. **Use correct table names:**
   - If error mentions a specific blocked table, ask about the corresponding allowed view
   - ❌ "base_customers_table" (internal)
   - ✓ "customers" (allowed view)

4. **Request access if needed:**
   - If you need access to blocked data, contact your administrator
   - Provide business justification
   - Security team will review and may grant access

**Debug steps:**
1. Note the disallowed table/column from the error message
2. Ask your administrator which table you should use instead
3. Rephrase your question using the approved table

---

### Issue: "rls_denied" Error

**Error message:**
```
Access to the requested data is denied by security policies. Your role or tenant
restrictions prevent you from accessing this data.
```

**Causes:**
1. Trying to access another tenant's/organization's data (most common)
2. Row-level security policy blocking based on your role/attributes
3. Accessing a view that requires a different role

**Solutions:**

1. **Verify you're asking about your own data:**
   - ❌ "Show me Acme Corp's orders" (if you're from TechCorp)
   - ✓ "Show me our orders" or "Show me orders" (auto-scoped to your tenant)

2. **Check your tenant context:**
   - Confirm your organization is set correctly
   - Check your JWT token includes the correct `tenant_id`
   - If wrong, contact your IT administrator

3. **Upgrade your role if needed:**
   - Some views require analyst or admin role
   - Request role upgrade from your manager/admin

4. **Check time-based restrictions:**
   - Some views may have time-based access controls
   - If blocked during certain hours, contact support

**Debug steps:**
1. Confirm your organization name (tenant_id)
2. Ask an admin to verify your role and permissions
3. Check if the requested data exists in your organization
4. If still blocked, include telemetry ID in support request

---

### Issue: "execution_timeout" Error

**Error message:**
```
Query execution timed out after 30 seconds. The query is requesting too much data
or performing too many complex operations.
```

**Causes:**
1. Querying all-time data without filtering
2. Requesting very large result sets
3. Complex joins or aggregations
4. System under load

**Solutions:**

1. **Add date filtering:**
   - ❌ Risky: "Show all orders"
   - ✓ Safe: "Show orders from the last 7 days"
   - Suggested ranges: today, last 7 days, last 30 days, year-to-date

2. **Limit the result set:**
   - ❌ Risky: "Show all customers"
   - ✓ Safe: "Show top 10 customers by revenue"
   - ✓ Safe: "Show the top 100 most recent transactions"

3. **Simplify the query:**
   - ❌ Complex: "Show me orders with customer details, products, payments, and invoices"
   - ✓ Simple: "Show me recent orders" (then ask about details separately)

4. **Try a smaller scope first:**
   - Start with "last 7 days" instead of "all time"
   - Start with "top 10" instead of "all"
   - Once working, can expand

5. **Reach out to support for large exports:**
   - If you legitimately need large amounts of data, contact support
   - They can provide batch exports or scheduled reports

**Debug steps:**
1. Ask the same question with a date range (e.g., "last 7 days")
2. If that works, gradually expand the date range
3. If still timing out, break into smaller queries
4. Contact support with telemetry ID if you need help

---

### Issue: "schema_unavailable" Error

**Error message:**
```
Schema metadata is temporarily unavailable. The system cannot access the
database schema right now.
```

**Causes:**
1. Database is temporarily down for maintenance
2. Network connectivity issue between app and database
3. Rare permission/configuration issue

**Solutions:**

1. **Wait a moment and retry:**
   - This is usually transient
   - Try again in 30 seconds

2. **Try a different, simpler query:**
   - Sometimes specific schema access fails
   - Try: "How many orders do we have?"
   - If that works, the database is responsive

3. **Check system status:**
   - Visit status.vizu.io (if available)
   - Look for maintenance windows
   - Check if there are known outages

4. **Contact support if it persists:**
   - Provide telemetry ID
   - Note the time you encountered the error
   - Include any error details from your application logs

---

### Issue: "internal_error" Error

**Error message:**
```
An unexpected error occurred. This is likely a server-side issue,
not a problem with your query. Please contact support with telemetry ID: [ID]
```

**Causes:**
1. Unexpected bug in the system
2. Unhandled edge case
3. Infrastructure issue

**Solutions:**

1. **Retry after a moment:**
   - Often a transient issue

2. **Try a similar but simpler question:**
   - If that works, the original question may trigger a bug
   - Include both in your support report

3. **Provide detailed information to support:**
   - Telemetry ID (required)
   - Exact question you asked
   - Steps to reproduce
   - Relevant context (role, tenant, time)

---

## Performance Issues (Slow but Successful Queries)

**Symptom:** Query completes but takes 10+ seconds

**Possible causes:**
1. Querying very large result set
2. Complex aggregation or join
3. Database is busy
4. Missing indices on frequently-queried columns

**Solutions:**

1. **Narrow the scope:**
   - Shorter date range
   - Fewer rows requested
   - Fewer joins

2. **Try during off-peak hours:**
   - If query is slow during business hours, try early morning/evening

3. **Report slow queries:**
   - Include telemetry ID
   - Include execution time
   - Include the question
   - System logs may show database performance details

---

## Unexpected Results (Wrong Data)

**Symptom:** Query completes and returns data, but it's not what you expected

**Possible causes:**
1. Query was rewritten for safety (tenant filter added)
2. Result is truncated/limited by role
3. Results are masked (PII hidden)
4. Date/time filtering applied
5. Query interpreted differently than intended

**Solutions:**

1. **Review the `caveats` field:**
   - Might explain why results are limited or masked
   - Example: "Result limited to 100 rows (role limit)"

2. **Check the actual SQL:**
   - The response includes the `sql` field
   - Review what query was actually executed
   - Verify it matches your intent

3. **Rephrase the question more specifically:**
   - Add filters (date, status, category)
   - Be more specific about what you want
   - Include numbers or thresholds if relevant

4. **Contact support if:**
   - You believe data is incorrect
   - Query is returning another tenant's data
   - Results are missing or incomplete
   - Include telemetry ID and expected vs. actual results

---

## Query Not Returning Expected Columns

**Symptom:** Query succeeds but doesn't include a column you expected

**Possible causes:**
1. Column is masked for your role
2. Column is restricted by RLS
3. Query was rewritten and column dropped
4. You asked about the wrong table

**Solutions:**

1. **Check the `columns` field:**
   - Response lists all returned columns
   - If your column isn't there, it's not available for your role

2. **Try asking explicitly:**
   - ❌ "Show customer data" (generic)
   - ✓ "Show me customer names and email addresses" (specific)

3. **Check your role:**
   - Some columns only available to analyst/admin
   - Request role upgrade if needed

4. **Ask about a different but related column:**
   - If `customer_id` is blocked, ask about `customer_name`
   - If `cost` is blocked, ask about `revenue`

---

## Getting Help

### When Contacting Support

**Always include:**
1. **Telemetry ID** — Copy from error response
2. **Your question** — Exact wording
3. **Expected vs. actual result** — What did you expect vs. what you got
4. **Your role and tenant** — For permission issues
5. **Time of occurrence** — For cross-referencing logs

**Helpful additions:**
- Screenshot of error message
- Any error details from application logs
- Steps to reproduce the issue
- Attempts you've already made to fix it

### Support Channels

- **Documentation:** Start with [README.md](README.md), [USAGE.md](USAGE.md), [FAQ.md](FAQ.md)
- **Logging & Telemetry:** Use telemetry ID to find detailed logs
- **Escalation:** Contact your organization's admin/support team
- **Critical Issues:** Email security@vizu.io with [SECURITY] tag

### Self-Service Steps

1. Check [README.md](README.md) for overview
2. Review [FAQ.md](FAQ.md) for common questions
3. Search this troubleshooting guide for your error code
4. Try rephrasing your question
5. Contact support with telemetry ID if still stuck
