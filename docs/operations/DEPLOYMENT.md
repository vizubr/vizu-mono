# Production Deployment Guide

This document covers deploying Vizu services to Google Cloud Run with proper secret management, monitoring, and operational procedures.

## Prerequisites

1. **GCP Project** with billing enabled
2. **gcloud CLI** authenticated: `gcloud auth login`
3. **Artifact Registry** repository for Docker images
4. **Secret Manager** API enabled
5. **Cloud Run** API enabled

## Initial Setup (One-Time)

### 1. Create GCP Resources

```bash
# Set project
export PROJECT_ID=your-project-id
export REGION=us-central1
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create vizu-images \
  --repository-format=docker \
  --location=$REGION \
  --description="Vizu service images"
```

### 2. Create Service Accounts

```bash
# Create service account for Cloud Run services
for SERVICE in atendente_core clients_api tool_pool_api analytics_api file_upload_api; do
  gcloud iam service-accounts create cloudrun-${SERVICE} \
    --display-name="Cloud Run ${SERVICE}"
done

# Grant Secret Manager access
for SERVICE in atendente_core clients_api tool_pool_api analytics_api file_upload_api; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:cloudrun-${SERVICE}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 3. Create Secrets

Create a `.env.production` file with real values (DO NOT commit this):

```bash
cp .env.production.example .env.production
# Edit .env.production with actual secret values
```

Then run the secret creation script:

```bash
chmod +x scripts/create_secrets.sh
./scripts/create_secrets.sh $PROJECT_ID .env.production
```

Verify secrets were created:

```bash
gcloud secrets list --project=$PROJECT_ID
```

### 4. Configure GitHub Actions

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

| Secret Name | Description |
|-------------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_SA_KEY` | Service account JSON key for CI/CD |
| `STAGING_ATENDENTE_URL` | Staging service URL (after first deploy) |
| `PRODUCTION_ATENDENTE_URL` | Production service URL (after first deploy) |

Add these variables:

| Variable Name | Value |
|---------------|-------|
| `GCP_REGION` | `us-central1` |
| `GAR_LOCATION` | `us-central1` |
| `GAR_REPOSITORY` | `vizu-images` |

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

Trigger a manual deployment via GitHub Actions:

1. Go to Actions → "Deploy to Cloud Run"
2. Click "Run workflow"
3. Select service and environment
4. Click "Run workflow"

Or deploy directly with gcloud:

```bash
# Build and push image
docker build -f services/atendente_core/Dockerfile -t $REGION-docker.pkg.dev/$PROJECT_ID/vizu-images/atendente_core:latest .
docker push $REGION-docker.pkg.dev/$PROJECT_ID/vizu-images/atendente_core:latest

# Deploy to Cloud Run
gcloud run deploy atendente_core-production \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/vizu-images/atendente_core:latest \
  --region=$REGION \
  --platform=managed \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,..." \
  --service-account=cloudrun-atendente_core@$PROJECT_ID.iam.gserviceaccount.com
```

## Monitoring

### Datadog Integration

Services are configured to send metrics, traces, and logs to Datadog when `DD_API_KEY` is set.

Key dashboards to set up:
- Service health overview
- Request latency (p50, p95, p99)
- Error rates by service
- Database connection pool metrics
- Redis memory usage

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
