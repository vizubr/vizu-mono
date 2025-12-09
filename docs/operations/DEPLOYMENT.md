# Production Deployment Guide

This document covers deploying Vizu services to Google Cloud Run with proper secret management, monitoring, and operational procedures.

## Prerequisites

1. **GCP Project** with billing enabled
2. **gcloud CLI** authenticated (or use GCP Console web UI)
3. **Artifact Registry** repository for Docker images
4. **Secret Manager** API enabled
5. **Cloud Run** API enabled
6. **Grafana Cloud** account for observability

## Initial Setup (One-Time)

### 1. Create GCP Resources via Console

If you don't have `gcloud` CLI, use the GCP Console:

1. **Enable APIs**: Go to APIs & Services → Enable APIs
   - Cloud Run API
   - Artifact Registry API  
   - Secret Manager API

2. **Create Artifact Registry**:
   - Go to Artifact Registry → Create Repository
   - Name: `vizu-images`
   - Format: Docker
   - Location: `southamerica-east1` (São Paulo)

3. **Create Service Accounts**:
   - Go to IAM & Admin → Service Accounts
   - Create one for CI/CD (e.g., `github-actions`)
   - Create one per service (e.g., `cloudrun-atendente-core`)

4. **Grant Permissions**:
   - CI service account needs: `Artifact Registry Writer`, `Cloud Run Admin`, `Secret Manager Accessor`
   - Service accounts need: `Secret Manager Secret Accessor`

### 2. Create Secrets in Secret Manager

Go to Security → Secret Manager and create these secrets:

| Secret Name | Description |
|-------------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `QDRANT_URL` | Qdrant Cloud URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `GRAFANA_OTLP_HEADERS` | `Authorization=Basic <base64>` |
| `OPENAI_API_KEY` | OpenAI API key (optional) |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional) |
| `GOOGLE_API_KEY` | Google AI API key |

### 3. Configure GitHub Repository

Go to GitHub → Repository → Settings → Secrets and variables → Actions

**Secrets** (sensitive):
| Secret | Description |
|--------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_SA_KEY` | JSON key for CI service account |

**Variables** (non-sensitive):
| Variable | Value |
|----------|-------|
| `GCP_REGION` | `southamerica-east1` |
| `GAR_LOCATION` | `southamerica-east1` |
| `GAR_REPOSITORY` | `vizu-images` |

### 4. Download Service Account Key for CI

1. Go to IAM & Admin → Service Accounts
2. Click on your CI service account
3. Keys → Add Key → Create new key → JSON
4. Copy the entire JSON content to GitHub secret `GCP_SA_KEY`

## Deployment

### Automatic Deployment (CI/CD)

Pushes to `main` automatically deploy to staging:

1. Code is pushed to `main`
2. Security scan runs (Trivy)
3. Images are built and pushed to Artifact Registry
4. Services are deployed to Cloud Run
5. Health checks validate deployment
6. On failure, automatic rollback executes

### Manual Deployment

Trigger via GitHub Actions:

1. Go to Actions → "Deploy to Cloud Run"
2. Click "Run workflow"
3. Select service and environment
4. Click "Run workflow"

## Monitoring with Grafana Cloud

### OTLP Configuration

Services send traces and metrics to Grafana Cloud via OTLP:

- **Endpoint**: `https://otlp-gateway-prod-sa-east-1.grafana.net/otlp`
- **Auth**: Basic auth with your Grafana Cloud instance ID and API key

### Setting up Grafana Dashboards

1. Go to Grafana Cloud → Dashboards
2. Import or create dashboards for:
   - Service health overview (from OTLP metrics)
   - Request latency (p50, p95, p99)
   - Error rates by service
   - Trace explorer (Tempo)

### Logs with Loki

Services output JSON logs compatible with Loki. To collect:

1. Set up Cloud Run log routing to Loki, OR
2. Use Grafana Agent in sidecar mode, OR
3. View logs directly in Cloud Run console

### Health Endpoints

Each service exposes:

| Endpoint | Purpose |
|----------|---------|
| `/health` | Comprehensive health check (for monitoring) |
| `/ready` | Readiness probe (for load balancers) |
| `/live` | Liveness probe (for orchestrators) |
| `/metrics` | Basic metrics |

Example health check response:

```json
{
  "status": "healthy",
  "service": "atendente_core",
  "version": "abc123",
  "environment": "production",
  "timestamp": "2025-12-09T10:30:00Z",
  "uptime_seconds": 3600.5,
  "checks": {
    "database": {"status": "ok", "duration_ms": 12.5},
    "redis": {"status": "ok", "duration_ms": 3.2}
  }
}
```

### Alerting

Configure alerts for:

1. **Service availability**: `/ready` returns non-200 for >1 minute
2. **Error rate**: >1% 5xx errors over 5 minutes
3. **Latency**: p95 latency >2s over 5 minutes
4. **Memory**: Container memory >80% for 5 minutes
5. **Security**: Any critical vulnerability detected

## Database Migrations

### Automatic (Recommended)

Migrations run automatically after production deployments via the `migrations` job in the CI workflow.

### Manual

```bash
# Via Cloud Run Job
gcloud run jobs execute db-migrations --region=$REGION --wait

# Or locally with Supabase CLI
cd libs/vizu_db_connector
supabase db push --linked
```

## Rollback Procedures

### Automatic Rollback

If health checks fail after deployment, the CI workflow automatically rolls back to the previous revision.

### Manual Rollback

```bash
# List revisions
gcloud run revisions list --service=atendente_core-production --region=$REGION

# Route traffic to previous revision
gcloud run services update-traffic atendente_core-production \
  --region=$REGION \
  --to-revisions=atendente_core-production-00042-xyz=100
```

## Incident Response

### Service Down

1. Check Cloud Run console for errors
2. Check Datadog for traces/logs
3. If needed, rollback to previous revision
4. Investigate root cause

### Database Issues

1. Check Supabase dashboard
2. Review connection pool metrics
3. Check for long-running queries
4. Scale connection pool if needed

### Security Incident

1. Rotate compromised secrets immediately
2. Update secrets in Secret Manager
3. Redeploy affected services
4. Review access logs
5. Document incident

## Environment Variables Reference

See `.env.production.example` for the complete list of environment variables. Key categories:

- **Database**: `DATABASE_URL`, `SUPABASE_*`
- **Cache**: `REDIS_URL`
- **LLM**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
- **Observability**: `DD_*`, `LANGFUSE_*`, `OTEL_*`
- **Auth**: `MCP_AUTH_GOOGLE_*`, `SUPABASE_JWT_SECRET`

## Security Checklist

Before going live:

- [ ] All secrets in Secret Manager (none in code/images)
- [ ] Trivy scans passing (no critical vulnerabilities)
- [ ] Service accounts have minimal permissions
- [ ] Network policies restrict unnecessary traffic
- [ ] Audit logging enabled
- [ ] Backup strategy documented and tested
- [ ] Incident response plan documented
- [ ] Team has access to monitoring dashboards
