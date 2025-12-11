# VIZU Cloud Run - Quick Reference

## The 3 Service Groups

```
┌──────────────────────────────────────────────────────┐
│ GROUP 1: agents-pool (PUBLIC ENTRY POINT)           │
│ ├─ atendente-core (8003) ← Main LLM agent          │
│ ├─ tool-pool-api (8004)  ← Tool orchestration      │
│ ├─ vendas-agent (8005)   ← Sales agent             │
│ └─ support-agent (8006)  ← Support agent           │
│ Memory: 2GB, Timeout: 3600s                        │
├──────────────────────────────────────────────────────┤
│ GROUP 2: workers-pool                               │
│ ├─ data-ingestion-worker (8007)                    │
│ ├─ file-processing-worker (8008)                   │
│ └─ file-upload-api (8009) ← Public                 │
│ Memory: 1-2GB, Scales 0-100                        │
├──────────────────────────────────────────────────────┤
│ GROUP 3: embedding-service                          │
│ └─ embedding-service (11435)                       │
│ Memory: 2GB, Concurrency: 50                       │
└──────────────────────────────────────────────────────┘
```

## Registry URL

```
us-east1-docker.pkg.dev/<YOUR_GCP_PROJECT_ID>/vizu/<service-name>:<tag>
```

## Quick Commands

### Local Development (3-group architecture)
```bash
# Start all services
make compose-cloud

# Stop all services
make compose-cloud-down

# View logs
docker compose -f docker-compose.cloud-run.yml logs -f
```

### Deploy to Cloud Run
```bash
# Deploy all
./scripts/deploy-cloud-run.sh all

# Deploy specific group
./scripts/deploy-cloud-run.sh agents-pool
./scripts/deploy-cloud-run.sh workers-pool
./scripts/deploy-cloud-run.sh embedding-service
```

### Check Service Status
```bash
# List all services
gcloud run services list --region=us-east1

# Get service URL
gcloud run services describe atendente-core --region=us-east1 --format='value(status.url)'

# View logs
gcloud run logs read atendente-core --region=us-east1 --limit=50
```

### Health Checks
```bash
# Local
curl http://localhost:8003/health  # atendente-core
curl http://localhost:8004/health  # tool-pool-api
curl http://localhost:11435/health # embedding-service

# Cloud Run
URL=$(gcloud run services describe atendente-core --region=us-east1 --format='value(status.url)')
curl "$URL/health"
```

## GitHub Actions Secrets Required

| Secret | Description |
|--------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_SA_KEY` | Base64-encoded service account key |
| `GCP_SA_EMAIL` | Service account email |

## Google Secret Manager Secrets Required

| Secret Name | Description |
|-------------|-------------|
| `database-url` | PostgreSQL connection string |
| `google-api-key` | Google AI API key |
| `supabase-key` | Supabase service key |
| `langfuse-secret` | Langfuse secret key |

## Key Files

| File | Purpose |
|------|---------|
| `.github/workflows/deploy-cloud-run.yml` | CI/CD workflow |
| `scripts/deploy-cloud-run.sh` | Manual deployment script |
| `docker-compose.cloud-run.yml` | Local 3-group testing |
| `docs/operations/CLOUD_RUN_DEPLOYMENT.md` | Full deployment guide |

## Estimated Costs

| Group | Monthly Cost |
|-------|--------------|
| agents-pool | $150-250 |
| workers-pool | $50-100 |
| embedding-service | $80-150 |
| **Total** | **$280-500** |
