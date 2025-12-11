# Cloud Run Deployment Guide

## Architecture Overview

Vizu monorepo deployed on **Google Cloud Run** as 4 main service groups:

```
┌─────────────────────────────────────┐
│     Cloud Load Balancer             │
│  (api.yourdomain.com)               │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┬──────────┬─────────┐
    │             │          │         │
┌───▼────┐  ┌────▼──┐  ┌───▼──┐  ┌───▼────┐
│Clients │  │Agents │  │Workers│  │Embedding
│ API    │  │Pool   │  │Pool   │  │Service
│(sync)  │  │(LLM)  │  │(async)│  │(shared)
└────────┘  └───────┘  └───────┘  └────────┘
```

---

## 1. Prerequisites

### GCP Project Setup

```bash
# Set your GCP project
export PROJECT_ID="your-gcp-project"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Create Artifact Registry

```bash
gcloud artifacts repositories create vizu \
  --repository-format=docker \
  --location=us-east1 \
  --description="Vizu services container images"
```

### Create Service Account

```bash
# Create service account for Cloud Run
gcloud iam service-accounts create vizu-cloud-run \
  --display-name="Vizu Cloud Run Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:vizu-cloud-run@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/run.admin

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:vizu-cloud-run@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:vizu-cloud-run@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/cloudsql.client
```

### Create GitHub Actions Service Account

```bash
# For GitHub Actions to authenticate
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions Deployment"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/artifactregistry.admin

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/run.admin

# Create key and download JSON
gcloud iam service-accounts keys create ~/github-key.json \
  --iam-account=github-actions@$PROJECT_ID.iam.gserviceaccount.com
```

---

## 2. Set Up GitHub Secrets

Add these to your repository settings (Settings → Secrets → Actions):

```bash
GCP_PROJECT_ID=your-gcp-project
GCP_SA_KEY=$(cat ~/github-key.json)  # Base64 encoded
GCP_SA_EMAIL=github-actions@PROJECT_ID.iam.gserviceaccount.com
```

---

## 3. Create Secrets in Google Secret Manager

```bash
# Database
gcloud secrets create database-url \
  --replication-policy="automatic" \
  --data-file=- <<< "postgresql://..."

# Supabase
gcloud secrets create supabase-key \
  --replication-policy="automatic" \
  --data-file=- <<< "eyJ..."

# API Keys
gcloud secrets create google-api-key \
  --replication-policy="automatic" \
  --data-file=- <<< "your-key"

gcloud secrets create langfuse-secret \
  --replication-policy="automatic" \
  --data-file=- <<< "sk-lf-..."

gcloud secrets create qdrant-api-key \
  --replication-policy="automatic" \
  --data-file=- <<< "your-key"
```

List secrets:
```bash
gcloud secrets list
```

---

## 4. Service Configuration Details

### clients-api
- **Purpose**: REST API for client management
- **Memory**: 1GB
- **Concurrency**: 100
- **Timeout**: 60s
- **Min instances**: 2 (always running)
- **Ingress**: internal-and-cloud-load-balancing
- **Services included**:
  - clients_api
  - clientes_finais_api
  - analytics_api
  - data_ingestion_api

### agents-pool
- **Purpose**: LLM agents (chat, conversations)
- **Memory**: 2GB
- **Concurrency**: 10 (low, LLM calls are heavy)
- **Timeout**: 3600s (1 hour max conversation)
- **Min instances**: 1 (cold starts OK for agents)
- **Ingress**: internal-and-cloud-load-balancing
- **Services included**:
  - atendente_core (main supervisor)
  - vendas_agent
  - support_agent
  - tool_pool_api (MCP)

### workers-pool
- **Purpose**: Async tasks, event-driven
- **Memory**: 1-2GB
- **Concurrency**: 20-50
- **Timeout**: 600-1800s (10-30 min tasks)
- **Min instances**: 0 (scale down when idle)
- **Ingress**: internal
- **Services included**:
  - data_ingestion_worker (Pub/Sub trigger)
  - file_processing_worker (async)
  - file_upload_api

### embedding-service
- **Purpose**: Shared embedding generation
- **Memory**: 2GB (model size)
- **Concurrency**: 50
- **Timeout**: 60s
- **Min instances**: 1 (called frequently)
- **Ingress**: internal (not public)

---

## 5. Networking & Load Balancing

### Cloud Load Balancer Setup

```bash
# Create backend service
gcloud compute backend-services create vizu-backend \
  --protocol=HTTP2 \
  --global \
  --health-checks=clients-api-health

# Add Cloud Run services as backends
gcloud compute backend-services add-backend vizu-backend \
  --instance-group=us-east1-clients-api-ig \
  --global \
  --balancing-mode=RATE
```

Or use **Cloud Run's built-in domain mapping**:

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service=clients-api \
  --domain=api.yourdomain.com \
  --region=us-east1
```

Then update DNS (your registrar):
```
api.yourdomain.com → ghs.googleusercontent.com (CNAME)
```

---

## 6. Deployment

### Manual Deployment (first time)

```bash
./scripts/deploy-cloud-run.sh
```

### Via GitHub Actions

```bash
# Push to main branch
git push origin main

# Or manually trigger
gh workflow run deploy-cloud-run.yml -f service=all
```

### Check Deployment

```bash
# List all services
gcloud run services list --region=us-east1

# Get service URL
gcloud run services describe clients-api \
  --region=us-east1 \
  --format='value(status.url)'

# View logs
gcloud run logs read clients-api --region=us-east1 --limit 50
```

---

## 7. Monitoring & Observability

### View Metrics

```bash
# CPU usage
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/request_count"'

# Check service health
gcloud run services describe clients-api --region=us-east1 --format=yaml
```

### Cloud Logging

```bash
# Tail logs
gcloud logging read "resource.service_name=clients-api" --limit 50 --format json

# Filter by severity
gcloud logging read "resource.service_name=clients-api AND severity=ERROR" --limit 20
```

### Set up Alerts

```bash
# High error rate alert
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Cloud Run Error Rate" \
  --condition="metric.type=run.googleapis.com/request_count AND metric.labels.response_code_class=5xx"
```

---

## 8. Cost Optimization

### By Service (estimated monthly)

| Service | vCPU-seconds | Memory-GB-seconds | Cost |
|---------|--------------|------------------|------|
| clients-api | 5M | 5M | ~$140 |
| agents-pool | 2M | 4M | ~$100 |
| workers-pool | 1M | 2M | ~$40 |
| embedding-service | 1M | 2M | ~$40 |
| **Total** | | | **~$320/mo** |

### Cost Reduction Tips

```bash
# Reduce min-instances for less-used services
gcloud run services update workers-pool \
  --min-instances=0 \
  --region=us-east1

# Set memory to exactly what's needed
gcloud run services update clients-api \
  --memory=512Mi \
  --region=us-east1

# Use Cloud Run with limited concurrency for long operations
gcloud run services update agents-pool \
  --concurrency=5 \
  --region=us-east1
```

---

## 9. Troubleshooting

### Service won't start

```bash
# Check logs
gcloud run logs read SERVICE_NAME --region=us-east1

# Common issues:
# - Missing environment variables (check --set-env-vars)
# - Missing secrets (check --set-secrets)
# - Memory too low (increase --memory)
```

### Slow startup/cold starts

```bash
# Increase min-instances to keep service warm
gcloud run services update SERVICE_NAME \
  --min-instances=2 \
  --region=us-east1
```

### Authentication errors

```bash
# Re-grant permissions
gcloud run services add-iam-policy-binding SERVICE_NAME \
  --member=serviceAccount:vizu-cloud-run@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/run.invoker \
  --region=us-east1
```

---

## 10. Scaling Configuration

For different traffic patterns:

### High Traffic (site + agents)
```bash
clients-api:
  - max-instances: 200
  - concurrency: 100
  - min-instances: 5

agents-pool:
  - max-instances: 100
  - concurrency: 10
  - min-instances: 2
```

### Medium Traffic
```bash
clients-api:
  - max-instances: 50
  - concurrency: 50
  - min-instances: 2

agents-pool:
  - max-instances: 20
  - concurrency: 10
  - min-instances: 1
```

### Low Traffic (dev/staging)
```bash
clients-api:
  - max-instances: 10
  - concurrency: 50
  - min-instances: 1

agents-pool:
  - max-instances: 5
  - concurrency: 5
  - min-instances: 0
```

---

## 11. Post-Deployment

1. **Update DNS** to point to Cloud Run domain
2. **Set up monitoring** in Cloud Console
3. **Test health endpoints**: `GET /health`, `GET /ready`, `GET /live`
4. **Check Pub/Sub** subscriptions for workers
5. **Verify secrets** rotation in Secret Manager
6. **Monitor costs** weekly
