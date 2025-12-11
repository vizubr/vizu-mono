# DigitalOcean Deployment - Architecture & Secrets Management

## Overview: Where Everything Lives

```
┌─────────────────────────────────────────────────────────────────┐
│                  Your Application                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SECRETS MANAGEMENT                                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. GitHub Secrets (CI/CD)                                │  │
│  │    - Container registry credentials                       │  │
│  │    - Deploy keys                                          │  │
│  │    - Slack/Discord webhooks                              │  │
│  │                                                            │  │
│  │ 2. .env.production (Droplet - /opt/vizu)                │  │
│  │    - Database credentials (Supabase)                     │  │
│  │    - Qdrant API key                                      │  │
│  │    - LLM API keys (Google, OpenAI, Anthropic)           │  │
│  │    - Langfuse credentials                                │  │
│  │    - Grafana Cloud credentials                           │  │
│  │    - Google OAuth secrets                                │  │
│  │    - Email service credentials                           │  │
│  │    - Twilio tokens                                       │  │
│  │    - Encryption keys                                     │  │
│  │                                                            │  │
│  │ 3. DigitalOcean App Spec (future - optional)            │  │
│  │    - Can manage secrets via DO console                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  DOCKER IMAGES                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Option A: DigitalOcean Container Registry                │  │
│  │  - Private registry included with DO account              │  │
│  │  - Free tier: $5/month                                    │  │
│  │  - URL: registry.digitalocean.com/your-name/vizu-*       │  │
│  │  - Built into Docker, easy authentication                │  │
│  │  - Integrated with DO droplets                           │  │
│  │                                                            │  │
│  │ Option B: Docker Hub (Free)                              │  │
│  │  - Public or private repos                                │  │
│  │  - 1 private repo free, then $5/month each               │  │
│  │  - URL: docker.io/yourname/vizu-*                       │  │
│  │  - Most compatibility, slower pulls                      │  │
│  │                                                            │  │
│  │ Option C: GitHub Container Registry (Free)              │  │
│  │  - Included with GitHub (no extra cost)                 │  │
│  │  - URL: ghcr.io/yourorg/vizu-*                          │  │
│  │  - Best for public repos                                │  │
│  │  - Integrated GitHub auth                                │  │
│  │                                                            │  │
│  │ Option D: Local Build (No Registry)                      │  │
│  │  - Build directly on droplet (slower)                    │  │
│  │  - docker compose build && up                            │  │
│  │  - No CI/CD, manual deployment only                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  PERSISTENT STORAGE                                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Docker Volumes (Droplet SSD)                             │  │
│  │  - HuggingFace model cache                               │  │
│  │  - Caddy SSL certificates                                │  │
│  │  - Application logs (optional)                           │  │
│  │                                                            │  │
│  │ DigitalOcean Spaces (Optional - S3 compatible)          │  │
│  │  - Document uploads from file_upload_api                 │  │
│  │  - Backup storage                                        │  │
│  │  - $5/month for 250GB                                    │  │
│  │                                                            │  │
│  │ Supabase (Already have)                                  │  │
│  │  - Database + Auth                                       │  │
│  │  - Included storage bucket                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

        ▼                          ▼                    ▼
    EXTERNAL SERVICES (Cloud)

    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  Supabase    │  │ Qdrant Cloud │  │ Grafana      │
    │  (Database)  │  │ (Vector DB)  │  │ (Monitoring) │
    ├──────────────┤  ├──────────────┤  ├──────────────┤
    │ PostgreSQL   │  │ Vector index │  │ OTLP tracing │
    │ Auth         │  │ Semantic     │  │ Logs         │
    │ Realtime     │  │ search       │  │ Metrics      │
    │ Storage      │  │              │  │              │
    └──────────────┘  └──────────────┘  └──────────────┘

    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Langfuse     │  │ Google AI    │  │ Email Svc    │
    │ (LLM traces) │  │ (Gemini API) │  │ (SendGrid    │
    ├──────────────┤  ├──────────────┤  │ or similar)  │
    │ Trace logs   │  │ LLM Model    │  ├──────────────┤
    │ Session mgmt │  │ Embeddings   │  │ Transactional│
    │ User mgmt    │  │              │  │ Marketing    │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 1. Secrets Management

### Where Secrets Go (The Strategy)

```
SECRETS HIERARCHY:
├── Development (.env local)
│   └── Same as production structure but with test credentials
│
├── GitHub Secrets (CI/CD only)
│   ├── Registry credentials (for pushing images)
│   └── Deploy keys (for pulling code)
│
└── Production (.env.production on Droplet)
    ├── Database: Supabase PostgreSQL + Auth
    ├── Vector DB: Qdrant Cloud API key
    ├── LLM: Google API key, OpenAI key, Anthropic key
    ├── Observability: Langfuse keys, Grafana Cloud headers
    ├── Email: SendGrid API key, Twilio token
    ├── OAuth: Google Client ID + Secret
    ├── Encryption: CREDENTIALS_ENCRYPTION_KEY
    └── Domain: DOMAIN (for Caddy SSL)
```

### Current State (in your .env)

Looking at your `.env`, you already have the structure:

```bash
# These stay in .env.production (on Droplet only):
DATABASE_URL=postgresql://...@...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_JWT_SECRET=...
QDRANT_URL_PROD=...
QDRANT_API_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_PUBLIC_KEY=...
MCP_AUTH_GOOGLE_CLIENT_ID=...
MCP_AUTH_GOOGLE_CLIENT_SECRET_DEV=...
TWILIO_AUTH_TOKEN=...
GRAFANA_API_KEY=glc_eyJvIjoiMTYxMzI3MyIs... (this one!)
```

**⚠️ IMMEDIATE ACTION NEEDED**: Your `GRAFANA_API_KEY` is visible in the `.env` attachment you just shared! This is like showing a password in public.

### Solution: Use GitHub Secrets for CI/CD

When you deploy to DO, you have **two paths**:

#### Path A: Manual Deployment (Simpler, recommended to start)
```
Your Laptop
    ↓
git push → GitHub (code only, no secrets)
    ↓
You SSH to Droplet
    ↓
git pull (code)
    ↓
Create .env.production manually (you paste secrets)
    ↓
docker compose up
```

**Secrets location**: `/opt/vizu/.env.production` (file on Droplet, NOT in git)

#### Path B: Automated Deployment with CI/CD (Later)
```
Your Laptop
    ↓
git push → GitHub
    ↓
GitHub Actions runs:
  1. Read registry credentials from GitHub Secrets
  2. Build Docker images
  3. Push to container registry
  4. SSH to Droplet
  5. Pull images
  6. Restart containers
    ↓
Droplet uses:
  - `.env.production` (local file)
  - Credentials from Docker registry login
```

---

## 2. Client Secrets (Google Auth, Email, etc.)

These are application-level secrets that users create (e.g., Google OAuth token for integration):

```
CLIENT CREDENTIALS FLOW:

Client (Browser/Mobile App)
    ↓
Gets Google OAuth flow → User authenticates
    ↓
Server receives short-lived token
    ↓
Server encrypts and stores in Supabase (credentials table)
    ↓
When needed:
  - Decrypt with CREDENTIALS_ENCRYPTION_KEY
  - Use to call Google API
  - Never expose to client
```

**Where these live**:
1. **Supabase Database** (`credentials` table) - encrypted with `CREDENTIALS_ENCRYPTION_KEY`
2. **In-memory cache** (Redis if you add it later) - for performance
3. **Never in git or logs**

Your app already handles this via the `tool_pool_api` service:
```python
# From your tool_pool_api
CREDENTIALS_ENCRYPTION_KEY=<fernet_key_base64>

# This key is used to:
# 1. Encrypt user's Google credentials before storing in DB
# 2. Decrypt them when making API calls
# 3. Rotate keys without losing data (future feature)
```

---

## 3. Docker Image Storage (Artifact Registry)

### DigitalOcean vs GCP Comparison

| Feature | GCP Artifact Registry | DO Container Registry | Docker Hub | GitHub Container Registry |
|---------|---|---|---|---|
| **Cost** | $0.10/GB stored | $5/month flat | $5/month/private repo | Free |
| **Setup** | Complex (gcloud) | Simple (DO console) | Very easy | GitHub integrated |
| **Speed** | Fast (GCP region) | Fast (DO network) | Variable | Very fast (GitHub) |
| **Private** | Yes | Yes | Yes (paid) | Yes |
| **Location** | Multi-region | Single region | Global | Global |
| **Best for** | Enterprise | DO users | Public images | Open source |

### Recommended: DigitalOcean Container Registry

**Why**: Already integrated, simple setup, cheap, fast for DO droplets

**Setup** (one-time):

```bash
# 1. Enable in DO Console
# Go to: https://cloud.digitalocean.com/registry
# Click "Get Started" → Create repository name: "vizu"
# Cost: $5/month for unlimited storage/bandwidth

# 2. On your laptop, authenticate Docker
doctl registry login

# 3. Build and push
docker build -t registry.digitalocean.com/your-username/vizu-atendente_core .
docker push registry.digitalocean.com/your-username/vizu-atendente_core

# 4. On Droplet, pull and run
docker pull registry.digitalocean.com/your-username/vizu-atendente_core
docker run ...
```

**GitHub Actions Integration** (later):

```yaml
# In .github/workflows/deploy.yml
- name: Authenticate to DO Container Registry
  run: |
    doctl registry login --expiry-seconds 600

- name: Build and push
  run: |
    docker build -t registry.digitalocean.com/your-username/vizu-${{ matrix.service }}:latest .
    docker push registry.digitalocean.com/your-username/vizu-${{ matrix.service }}:latest

- name: Deploy to Droplet
  run: |
    ssh vizu@droplet-ip "docker pull registry.digitalocean.com/your-username/vizu-*:latest"
    ssh vizu@droplet-ip "docker compose -f docker-compose.prod.yml up -d"
```

### Alternative: GitHub Container Registry (FREE!)

If you don't want to pay for DO registry:

```bash
# 1. Create GitHub personal access token with `write:packages`
# Go to: https://github.com/settings/tokens

# 2. Authenticate
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# 3. Build and push
docker build -t ghcr.io/vizubr/vizu-atendente_core:latest .
docker push ghcr.io/vizubr/vizu-atendente_core:latest

# 4. On Droplet
docker pull ghcr.io/vizubr/vizu-atendente_core:latest
```

### Alternative: Docker Hub (Cheap, Easy)

```bash
# 1. Create account at hub.docker.com

# 2. Authenticate
docker login

# 3. Build and push
docker build -t your-username/vizu-atendente_core:latest .
docker push your-username/vizu-atendente_core:latest
```

---

## 4. Persistent Storage

### Docker Volumes (Droplet SSD)

```yaml
# In docker-compose.prod.yml
volumes:
  huggingface_cache:      # HuggingFace models (~2GB)
  caddy_data:             # SSL certificates
  caddy_config:           # Caddy config
```

These are stored on the Droplet's SSD filesystem at `/var/lib/docker/volumes/`.

**Cost**: Included with Droplet

### Document Storage (File Upload API)

**Option A: Supabase Storage** (Included)
```python
# In file_upload_api
supabase.storage.from_("documents").upload(path, file_buffer)
# Free 1GB, then per-request pricing
```

**Option B: DigitalOcean Spaces** (S3-compatible)
```python
# Like AWS S3 but cheaper
# Cost: $5/month for 250GB
# Setup:
s3_client = boto3.client(
    's3',
    endpoint_url='https://nyc3.digitaloceanspaces.com',
    aws_access_key_id=os.environ['DO_SPACES_KEY'],
    aws_secret_access_key=os.environ['DO_SPACES_SECRET']
)
s3_client.upload_file('file.pdf', 'vizu-documents', 'path/to/file.pdf')
```

**Recommendation**: Start with **Supabase Storage** (included), add Spaces later if needed.

---

## 5. Complete Secrets Checklist for Production

### Place A: GitHub Secrets (for CI/CD)

```
REGISTRY_USERNAME = your-username (DO/Docker Hub)
REGISTRY_PASSWORD = registry-token
DEPLOY_SSH_KEY = SSH private key for Droplet
DO_SPACES_KEY = DigitalOcean Spaces access key (optional)
DO_SPACES_SECRET = DigitalOcean Spaces secret (optional)
```

### Place B: .env.production (on Droplet, NEVER in git)

```bash
# Database
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_JWT_SECRET=...

# Vector DB
QDRANT_URL=https://...
QDRANT_API_KEY=...

# LLM Providers
LLM_PROVIDER=google
GOOGLE_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...

# Observability
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-sa-east-1.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64>

# OAuth & Auth
MCP_AUTH_GOOGLE_CLIENT_ID=...
MCP_AUTH_GOOGLE_CLIENT_SECRET_DEV=...

# Email & Communication
TWILIO_AUTH_TOKEN=...
SENDGRID_API_KEY=... (if using SendGrid)

# Security
CREDENTIALS_ENCRYPTION_KEY=... (32-byte hex)

# Domain
DOMAIN=api.yourdomain.com
```

---

## Architecture Decision Tree

```
DO YOU WANT...?
│
├─ Automated CI/CD?
│  ├─ YES → Use DO Container Registry ($5/mo) + GitHub Actions
│  └─ NO  → Manual builds on Droplet (slower, simpler)
│
├─ Need to store user documents?
│  ├─ < 1GB → Use Supabase Storage (free)
│  ├─ 1-250GB → Use DO Spaces ($5/mo)
│  └─ > 250GB → Use S3 or add another Spaces bucket
│
├─ Want high availability later?
│  ├─ YES → Plan for K8s or multiple droplets
│  └─ NO  → Single droplet is fine for now
│
└─ Budget conscious?
   ├─ YES → GitHub Container Registry (free) + Supabase Storage
   └─ NO  → DO Container Registry + DO Spaces
```

---

## Summary: Where Everything Lives

| Component | Location | Cost | Notes |
|-----------|----------|------|-------|
| **Application Code** | GitHub repo | Free | .gitignore: .env.production |
| **Container Images** | DO Registry or GHCR | $5/mo or Free | Built from CI or manually |
| **Application Secrets** | .env.production on Droplet | Free | SSH access only, chmod 600 |
| **CI/CD Secrets** | GitHub Secrets | Free | Registry credentials, deploy keys |
| **Database** | Supabase | Free tier | PostgreSQL + Auth |
| **Vector DB** | Qdrant Cloud | Paid | API key in .env.production |
| **Document Storage** | Supabase Storage or DO Spaces | Free/5mo | For file_upload_api outputs |
| **User Credentials** | Supabase DB (encrypted) | Free tier | Encrypted with CREDENTIALS_ENCRYPTION_KEY |
| **SSL Certificates** | Caddy (auto-renews) | Free | Let's Encrypt |
| **Monitoring** | Grafana Cloud + Langfuse | Paid | API keys in .env.production |

---

## Next Steps

1. **Secrets**: Update `.env.production.example` to match your actual secrets list (I can help)
2. **Registry**: Choose DO Container Registry or GHCR and set up auth
3. **Encryption Key**: Generate a proper `CREDENTIALS_ENCRYPTION_KEY`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
4. **First Deployment**: Follow the deployment guide with manual setup
5. **Later**: Add CI/CD pipeline for automated builds/deployments

Want me to create a deployment checklist or CI/CD workflow next?
