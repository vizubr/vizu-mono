# Text-to-SQL Tool Operations Runbook

## Quick Reference

### On-Call Escalation Path
1. **Alert triggered** → Check dashboard for context
2. **Determine severity** → Follow severity response below
3. **Engage team** → Page/notify based on alert severity
4. **Document** → Create incident ticket
5. **Resolve** → Follow troubleshooting steps
6. **Postmortem** → Root cause analysis within 24 hours

### Alert Severity Response

| Severity | Response | SLA |
|----------|----------|-----|
| CRITICAL | Page on-call immediately | 5 min |
| WARNING | Create ticket, notify team | 30 min |
| INFO | Log and monitor | N/A |

---

## Critical Alert Responses

### Cross-Tenant Data Leakage (CRITICAL)

**Symptoms:**
- Alert: "Cross-tenant data leakage detected"
- Multiple users from different tenants accessing each other's data
- Validation bypassed in favor of RLS

**Immediate Actions:**
1. Page on-call engineer immediately
2. Check dashboard for: which tenants affected, how many queries, duration
3. Pull audit logs: telemetry IDs of affected queries
4. Check RLS policies: verify they're still enforced
5. Kill long-running queries if needed

**Investigation:**
```bash
# Check for cross-tenant access patterns
SELECT tenant_id, COUNT(*) as cnt
FROM audit_logs
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY tenant_id
HAVING COUNT(*) > baseline

# Review affected queries
SELECT telemetry_id, sql_query, tenant_id, result_count
FROM audit_logs
WHERE telemetry_id IN (...)
```

**Response:**
- If confirmed: Immediately kill affected queries
- Restart text-to-sql service (if needed)
- Notify affected customers
- Roll back any bad data changes
- Post-incident: review RLS policies, allowlist, query validation

**Documentation:**
- Create incident ticket with: duration, affected tenants, number of leaked rows, root cause, fix applied

---

### Query Success Rate Low (CRITICAL)

**Symptoms:**
- Alert: "Query success rate is X% (threshold: 95%)"
- Users report "all my queries are failing"
- Error logs spike

**Immediate Actions:**
1. Check which errors are happening most (LLM? Validation? RLS?)
2. Verify database is healthy: connectivity, disk space, CPU
3. Check if recent changes were deployed (allowlist? schema?)
4. Review error logs for patterns

**Investigation:**
```bash
# Check error distribution
SELECT error_code, COUNT(*) as cnt
FROM audit_logs
WHERE timestamp > NOW() - INTERVAL '15 minutes'
GROUP BY error_code

# Check most recent deploy
git log --oneline -10

# Check database health
SELECT ...  -- CPU, memory, connections
```

**Response:**
- **LLM issues**: Check LLM service health, restart if needed
- **Validation issues**: Check if allowlist changed recently, revert if needed
- **Database issues**: Check connectivity, disk space, check for long locks
- **Schema issues**: Check if recent migrations broke views
- **Roll back**: If recent deploy caused it, roll back

---

### RLS Denial Rate Spike (CRITICAL)

**Symptoms:**
- Alert: "RLS denial rate spiked 10x"
- Legitimate users getting "access denied" errors
- `rls_denied` errors in logs

**Immediate Actions:**
1. Pull RLS denial logs: affected users, which tables, which tenants
2. Check if JWT tokens changed or user permissions were modified
3. Verify RLS policies are in sync with allowlist
4. Check if schema changes affected RLS policies

**Investigation:**
```bash
# Check RLS denial pattern
SELECT user_id, table_accessed, COUNT(*) as denials
FROM audit_logs
WHERE error_code = 'rls_denied'
  AND timestamp > NOW() - INTERVAL '15 minutes'
GROUP BY user_id, table_accessed

# Verify RLS policy
SELECT * FROM information_schema.role_table_grants
WHERE table_schema = 'public'
```

**Response:**
- Coordinate with auth team: verify JWT token claims
- Check if user roles changed (should be in audit trail)
- Verify RLS policies match current allowlist
- If RLS was recently modified, test in staging first before production rollback

---

### Unauthorized Table Access Attempt (CRITICAL)

**Symptoms:**
- Alert: "Attempted access to unauthorized table: X by role Y"
- LLM generated SQL referencing disallowed view
- Query validation caught it but indicates LLM error

**Immediate Actions:**
1. Find the query in audit logs
2. Check if it was blocked (validation_failed) or leaked (allowed through)
3. Review the question and generated SQL
4. Determine if it's a LLM hallucination or allowlist misconfiguration

**Investigation:**
```bash
# Find the attempted query
SELECT telemetry_id, question, sql_query, validation_passed
FROM audit_logs
WHERE table_accessed = 'disallowed_table'
  AND timestamp > NOW() - INTERVAL '5 minutes'

# Check LLM model version
# Check allowlist configuration
```

**Response:**
- **LLM hallucination**: Document for LLM team (add to prompt hardening)
- **Allowlist misconfiguration**: Verify allowlist is correct
- **Blocked successfully**: No action needed, system working as designed
- **Leaked through**: CRITICAL - investigate validation bypass

---

## Warning Alert Responses

### Validation Failure Rate High (WARNING)

**Response Steps:**
1. Check breakdown of validation failures
2. Find common patterns (which views? which error types?)
3. Investigate root cause:
   - Allowlist misconfigured?
   - Schema recently changed?
   - LLM asking about wrong tables?
4. Ticket to fix the root cause
5. Update docs/examples if allowlist changed

**Investigation:**
```bash
SELECT error_reason, COUNT(*) as cnt
FROM audit_logs
WHERE validation_passed = false
  AND timestamp > NOW() - INTERVAL '15 minutes'
GROUP BY error_reason
```

---

### Timeout Rate High (WARNING)

**Response Steps:**
1. Pull slow queries: execution time, view, tenant
2. Check if specific views are slow (missing index?)
3. Check if database is under load (CPU, memory, connections)
4. Consider implementing time-based restrictions

**Investigation:**
```bash
SELECT view_name, AVG(execution_time_ms) as avg_time, MAX(execution_time_ms) as max_time
FROM audit_logs
WHERE timestamp > NOW() - INTERVAL '10 minutes'
GROUP BY view_name
HAVING AVG(execution_time_ms) > 5000
```

**Response:**
- Create ticket for index recommendations
- Consider adding timeout to specific heavy views
- Notify users to use date filters
- Escalate if pattern continues

---

### LLM Hallucination Rate High (WARNING)

**Response Steps:**
1. Identify common hallucination patterns
2. Review questions that triggered hallucinations
3. Update LLM prompt with more constraints
4. Consider adding these table names to blocklist

**Investigation:**
```bash
SELECT sql_query, question, COUNT(*) as occurrences
FROM audit_logs
WHERE attempted_disallowed_table = true
  AND timestamp > NOW() - INTERVAL '30 minutes'
GROUP BY sql_query, question
ORDER BY occurrences DESC
```

---

## Common Troubleshooting

### Users Can't Query Certain Views

**Steps:**
1. Confirm view exists in schema: `SELECT * FROM information_schema.views WHERE table_name = '...'`
2. Check if view is in allowlist for user's role
3. Check if user has permission (via RLS)
4. Review recent schema/allowlist changes

**Fix:**
- Add view to allowlist (requires review + approval)
- Grant RLS permissions
- Update docs with new view availability

---

### Queries Taking Too Long

**Steps:**
1. Identify slow view
2. Check if index exists on filter columns
3. Check result set size
4. Check database load

**Fix:**
- Create index on frequently-filtered columns
- Add LIMIT or date-based filtering
- Optimize view definition (if possible)
- Contact users to narrow query scope

---

### LLM Keeps Asking About Internal Tables

**Steps:**
1. Find pattern in audit logs
2. Extract the user questions causing it
3. Analyze why LLM chose those tables
4. Update LLM prompt to exclude them

**Fix:**
- Add to LLM system prompt
- Add to validation blocklist (for safety)
- Document in FAQ which tables are off-limits

---

### All Queries Failing with Internal Error

**Steps:**
1. Check service health: text-to-sql service running?
2. Check database: connectivity, schema accessible?
3. Check LLM service: responding?
4. Check logs for exceptions

**Restart Procedure:**
```bash
# Restart service
kubectl rollout restart deployment/vizu-text-to-sql -n production

# Or if not Kubernetes
systemctl restart vizu-text-to-sql

# Wait for health check
curl http://localhost:8000/health
```

---

## Weekly Checks

Every Monday morning, verify:

1. **Dashboard health** — No ongoing warning alerts
2. **Performance metrics** — p95 latency < 5s, success rate > 95%
3. **Error logs** — No unusual patterns
4. **Audit logs retention** — > 7 days available
5. **Allowlist changes** — Review any modifications from past week
6. **RLS policies** — Verify in sync with allowlist

---

## Monthly Tasks

1. **Full schema audit** — Compare schema vs. allowlist, document drift
2. **Performance review** — Slow query analysis, index recommendations
3. **LLM quality review** — Sample generated queries, measure accuracy
4. **Cost review** — LLM token usage, database quota
5. **Security audit** — Review for unauthorized access attempts
6. **Documentation review** — Ensure SECURITY.md, FAQ.md match reality

---

## Quarterly Review

1. **Capacity planning** — Growth in query volume, data size
2. **Allowlist comprehensive review** — Ensure current state is documented
3. **Incident postmortems** — Review all Q incidents, identify patterns
4. **SLO review** — Adjust targets based on historical data
5. **Architecture review** — Evaluate if current system meets needs

---

## Escalation Contacts

| Role | Contact | On-Call | Backup |
|------|---------|---------|--------|
| On-Call Engineer | PagerDuty | + escalation policy | Backup engineer |
| Database Admin | DBA Team | Rotation | Lead DBA |
| LLM/AI Team | AI Lead | Slack #ai-oncall | Platform team |
| Security | Security Team | + if data leak involved | CISO |

## Emergency Contacts

- **Data Breach/Leakage**: security@vizu.io (immediate)
- **Service Down**: #incident-response Slack + page on-call
- **CEO/Legal**: Only if data breach confirmed

---

## Playbooks

### Data Leak Incident

1. **Immediate** (first 5 min):
   - Confirm leak: what data, which tenants, how many rows?
   - Kill affected queries: `SELECT pg_terminate_backend(...)`
   - Disable SQL tool if necessary

2. **Short-term** (first hour):
   - Collect evidence: audit logs, RLS policies, query logs
   - Notify security team
   - Notify affected customers (unless internal-only)
   - Begin root cause analysis

3. **Medium-term** (first day):
   - Complete root cause analysis
   - Implement fix (RLS policy? Validation? Code?)
   - Deploy fix to production
   - Verify fix with test queries

4. **Long-term** (next week):
   - Post-incident review with team
   - Update controls to prevent recurrence
   - Customer notification follow-up
   - Board/Legal briefing if needed

### Availability Issue (All Queries Failing)

1. **Immediate** (first 2 min):
   - Check service health: text-to-sql service up?
   - Check database: ping, connections, queries working?
   - Check LLM service: responding?

2. **Investigation** (first 15 min):
   - Check recent deployments
   - Check error logs for patterns
   - Check metrics: CPU, memory, disk space
   - Check if upstream services are down

3. **Resolution**:
   - Restart service (if hung)
   - Revert recent deploy (if bad code)
   - Check database (if connectivity issue)
   - Escalate to dependent services if needed

### Slow Performance

1. **Investigation**:
   - Which queries are slow?
   - Is it database slow or application slow?
   - Is it LLM slow or SQL execution?
   - Is it all users or specific tenant?

2. **Resolution**:
   - Add indices (if database)
   - Add caching (if repeated queries)
   - Optimize view (if schema issue)
   - Reduce query scope (if user query too broad)
