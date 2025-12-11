# Vizu Cloud Run Architecture & Decision Guide

## Executive Summary

Your monorepo with **15 microservices** is deployed on **Google Cloud Run** as **4 service groups**:

| Group | Services | Memory | Concurrency | Timeout | Est. Cost/mo |
|-------|----------|--------|-------------|---------|--------------|
| **clients-api** | 4 REST APIs | 1GB | 100 | 60s | ~$140 |
| **agents-pool** | 4 LLM agents | 2GB | 10 | 3600s | ~$100 |
| **workers-pool** | 4 async workers | 1-2GB | 20-50 | 10-30min | ~$40 |
| **embedding-service** | 1 shared svc | 2GB | 50 | 60s | ~$40 |
| **TOTAL** | **15** | | | | **~$320/mo** |

---

## Why This Architecture?

### Why NOT Single Container?
```
❌ One big Docker image with all 15 services
   - Memory bloat (need 8GB+ VM)
   - One service crashes = everything fails
   - Can't scale independently
   - Long cold starts
   - Complex logging & debugging
```

### Why NOT 15 Separate Cloud Runs?
```
❌ One Cloud Run per service
   - Cost: $40-50 per service x 15 = $600-750/mo
   - Operational complexity (manage 15 deployments)
   - Many don't need independent scaling
   - Over-engineered
```

### Why These 4 Groups?

**1. clients-api** (4 services together)
- All stateless sync operations
- Similar resource profile (1GB)
- Same scaling pattern (high concurrency, low timeout)
- Share database connections
- Can be deployed together

**2. agents-pool** (4 services together)
- All LLM-based, CPU-heavy
- All need long timeouts (3600s for conversations)
- Low concurrency (LLM calls are sequential)
- Share conversation memory/state
- Benefit from co-location

**3. workers-pool** (3-4 services together)
- All asynchronous/event-driven
- Can scale independently from sync APIs
- Can be 0 instances when idle (save cost)
- Share task queue infrastructure

**4. embedding-service** (standalone)
- Shared by multiple services (agents, workers)
- Separate memory needs (HuggingFace model)
- Internal only (no public access)
- Easier to version independently

---

## Service Dependency Map

```
┌─────────────────────────────────────────────────────────┐
│                     Client Requests                      │
│                  (HTTPS via Cloud LB)                   │
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────┴────────────────┬──────────────┐
       │                        │              │
   ┌───▼────────────────┐  ┌───▼──────┐  ┌──▼─────────┐
   │   clients-api      │  │ agents   │  │ workers    │
   │   (REST, sync)     │  │ (LLM)    │  │ (async)    │
   │                    │  │          │  │            │
   │ - clients_api      │  │- atendente_core         │
   │ - clientes_finais  │  │- vendas_agent          │
   │ - analytics_api    │  │- support_agent         │
   │ - data_ingestion   │  │- tool_pool_api (MCP)   │
   └────────┬───────────┘  └──┬──────┘  └─┬──────────┘
            │                 │           │
            │  ┌──────────────┼───────────┘
            │  │              │
            └──┼──────────────┼──────────┐
               │              │          │
          ┌────▼──────┬────────▼───┐  ┌─▼──────────┐
          │  Supabase │  Qdrant    │  │ Embedding  │
          │           │  Cloud     │  │ Service    │
          │ Database  │  Vector DB │  │            │
          └───────────┴────────────┘  └────────────┘
                │
                │
          ┌─────▼──────────┐
          │  Pub/Sub       │
          │  Topics        │
          │  (workers)     │
          └────────────────┘
```

---

## Network Flow

```
User Request
    │
    ├──[HTTPS]──> Cloud Load Balancer
    │              (api.yourdomain.com)
    │
    ├─────────────────────────────────────┐
    │                                     │
[Internal Traffic - Cloud Run Services]
    │
    ├──[REST APIs]─> clients-api (sync)
    │   • Returns in < 1 second
    │   • High concurrency (100+)
    │   • Always 2+ instances running
    │
    ├──[gRPC/HTTP]──> agents-pool (LLM)
    │   • Long conversations (up to 1 hour)
    │   • Low concurrency (10 max)
    │   • Calls tool_pool_api for functions
    │
    ├──[Events]──> workers-pool (async)
    │   • Triggered by Pub/Sub
    │   • Scales 0-100 based on queue depth
    │   • Calls embedding-service for vectors
    │
    └──[HTTP]──> embedding-service (shared)
        • Internal only
        • 2GB model in memory
        • 50 concurrent requests
```

---

## Deployment Flow

### First Time Setup

```bash
# 1. Create GCP project and enable APIs
export PROJECT_ID="your-project"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# 2. Create Artifact Registry
gcloud artifacts repositories create vizu --repository-format=docker

# 3. Create service account
gcloud iam service-accounts create vizu-cloud-run

# 4. Add GitHub secrets (GCP_PROJECT_ID, GCP_SA_KEY)

# 5. Create secrets in Secret Manager
gcloud secrets create database-url --data-file=- <<< "postgresql://..."
gcloud secrets create google-api-key --data-file=- <<< "your-key"
```

### On Push to `main`

```
GitHub Push
    │
    └──> .github/workflows/deploy-cloud-run.yml
         │
         ├──> Matrix build (4 service groups)
         │    • Build Docker images
         │    • Push to Artifact Registry
         │
         └──> Deploy to Cloud Run
              • clients-api (1 service group)
              • agents-pool (4 agent services)
              • workers-pool (3 worker services)
              • embedding-service (1 shared service)
```

---

## Cost Breakdown

### Factors

| Factor | Impact |
|--------|--------|
| **vCPU-seconds** | $0.000024 per second |
| **Memory-GB-seconds** | $0.000004 per second |
| **Requests** | First 2M free, $0.40 per 1M after |

### Estimated Monthly (1M requests + normal usage)

```
clients-api (sync, 1 hour/day active):
  - 100 requests/sec × 3600s × 30 days = 10.8B vCPU-sec
  - Memory: same as CPU-sec × 1GB = 10.8B GB-sec
  - Cost: (10.8B × $0.000024) + (10.8B × $0.000004) = ~$308

agents-pool (low traffic, always 1 min instance):
  - 1000 vCPU-sec/day for min instance = 30,000/month
  - Long calls (avg 1 min/call, 100 calls/day) = 10,800 vCPU-sec
  - Cost: ~$100

workers-pool (0 instances when idle):
  - 50 tasks/day × 300 sec = 1.5M vCPU-sec/month
  - Cost: ~$50

embedding-service (1 min instance + calls):
  - Min instance: ~300 vCPU-sec/day = 9,000/month
  - Calls: ~500/day × 10 sec = 150,000/month
  - Cost: ~$40

TOTAL: ~$500/month
```

**To optimize:**
- Reduce min-instances where possible
- Use Cloud Run's autoscaling aggressively
- Monitor and adjust concurrency limits
- Consider using Vertex AI for embeddings instead of local model

---

## Key Configuration Details

### clients-api
```yaml
Memory: 1Gi
CPU: 2
Concurrency: 100
Timeout: 60s
Min instances: 2     # Always running (low cost, critical service)
Max instances: 100
Ingress: public      # Load balancer → external users
Allow unauthenticated: true
```

**When to scale:**
- If p99 latency > 500ms, increase concurrency to 150
- If errors increase, check database connection pool

### agents-pool
```yaml
Memory: 2Gi          # LLM + conversation history
CPU: 2
Concurrency: 10      # Low, sequential LLM calls
Timeout: 3600s       # 1 hour max conversation
Min instances: 1     # Can be 0 to save $, but cold starts hurt UX
Max instances: 50
Ingress: internal + load balancer
```

**When to scale:**
- High queue depth: increase max-instances to 100
- Cold starts problematic: increase min-instances to 2
- Memory pressure: add swap disk or split into 2 services

### workers-pool
```yaml
Memory: 1-2Gi
CPU: 2
Concurrency: 20-50
Timeout: 600-1800s (10-30 min per task)
Min instances: 0     # Scale down when idle (saves cost)
Max instances: 100
Ingress: internal    # Pub/Sub triggers, not public
```

**When to scale:**
- If Pub/Sub queue grows: increase max-instances
- If tasks timeout: increase timeout or split into smaller jobs

### embedding-service
```yaml
Memory: 2Gi          # HuggingFace model size
CPU: 2
Concurrency: 50
Timeout: 60s
Min instances: 1     # Model takes time to load
Max instances: 50
Ingress: internal    # Called by agents + workers
```

**When to scale:**
- If queue depth > 1000: increase concurrency or min-instances
- High latency: profile Python code, check GC pauses

---

## Monitoring & Alerting

### Key Metrics to Watch

```bash
# CPU usage
gcloud monitoring read "metric.type=run.googleapis.com/request_count" \
  --filter='resource.service_name="clients-api"' \
  --format=json

# Error rate
gcloud logging read "resource.service_name=clients-api AND severity=ERROR" \
  --limit=50

# Cold start latency (p95)
gcloud logging read "resource.service_name=agents-pool AND logName:request_logs" \
  --limit=100 | jq '.latencies | sort | .[length-5:]'
```

### Alerts to Set Up

1. **Error rate > 1%** → Page on-call
2. **P95 latency > 5s** (clients-api) → Warn, scale up
3. **P95 latency > 30s** (agents-pool) → Warn, might be LLM issue
4. **Pub/Sub queue depth > 10k** (workers) → Scale up workers
5. **Cold starts > 30s** (agents) → Consider persistent instance

---

## Migration Path (If Switching Back to DigitalOcean)

If Cloud Run doesn't work out, you can quickly switch back:

```bash
# DigitalOcean setup would be:
USE_GHCR=true
docker compose -f docker-compose.prod.yml up -d

# Key differences:
# - Use .env.production file (instead of Secret Manager)
# - Caddy for reverse proxy (vs Cloud Load Balancer)
# - Manual scaling (vs auto-scaling)
# - Simpler but less resilient
```

---

## Next Steps

1. **Set up GCP project**
   ```bash
   export PROJECT_ID="your-project"
   cd docs/operations
   # Follow CLOUD_RUN_DEPLOYMENT.md steps 1-3
   ```

2. **Create GitHub secrets**
   - `GCP_PROJECT_ID`
   - `GCP_SA_KEY` (base64 JSON)
   - `GCP_SA_EMAIL`

3. **Create Secret Manager secrets**
   ```bash
   gcloud secrets create database-url --data-file=- <<< "$DATABASE_URL"
   gcloud secrets create google-api-key --data-file=- <<< "$GOOGLE_API_KEY"
   # etc.
   ```

4. **Test deployment**
   ```bash
   # Manual deployment
   chmod +x scripts/deploy-cloud-run.sh
   ./scripts/deploy-cloud-run.sh all

   # Or trigger GitHub Actions
   git push origin main
   ```

5. **Set up monitoring**
   - Enable Cloud Logging
   - Create uptime checks for /health endpoints
   - Set up billing alerts

6. **Test health endpoints**
   ```bash
   curl https://api.yourdomain.com/health
   curl https://api.yourdomain.com/ready
   curl https://api.yourdomain.com/live
   ```
