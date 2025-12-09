# Secrets Management Checklist

Use this to organize all your secrets before deploying to DigitalOcean.

## ✅ Before You Start

- [ ] Have a DigitalOcean account
- [ ] Have Supabase credentials
- [ ] Have Qdrant Cloud credentials
- [ ] Have Grafana Cloud instance (optional but recommended)
- [ ] Have Langfuse account
- [ ] Have a domain name
- [ ] Can SSH to your Droplet

---

## 🗝️ Part 1: Application Secrets (for `.env.production`)

### Database (Supabase)

```bash
# Get these from: https://app.supabase.com/project/[ref]/settings/api
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_KEY=eyJ...  # anon/public key

# For backend services
SUPABASE_SERVICE_KEY=eyJ...  # service_role key - KEEP SECRET!
SUPABASE_JWT_SECRET=...  # From Settings > API > JWT Settings

# Full connection string for Python apps
# Format: postgresql://postgres:[password]@[host]:[port]/postgres
DATABASE_URL=postgresql://postgres:[PASSWORD]@[PROJECT-REF].pooler.supabase.com:6543/postgres
```

**How to get these**:
1. Go to https://app.supabase.com/project/[your-project]/settings/api
2. Copy "Project URL" → `SUPABASE_URL`
3. Copy "anon public" → `SUPABASE_KEY`
4. Copy "service_role secret" → `SUPABASE_SERVICE_KEY` (⚠️ KEEP SECRET)
5. Go to Settings > API > JWT Settings, copy secret → `SUPABASE_JWT_SECRET`
6. Go to Settings > Database, copy connection string → `DATABASE_URL`

---

### Vector Database (Qdrant Cloud)

```bash
# Get these from: https://cloud.qdrant.io
QDRANT_URL=https://[cluster-id].sa-east-1.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=...  # API key from dashboard
```

**How to get these**:
1. Go to https://cloud.qdrant.io
2. Click on your cluster
3. Copy "Vector URL" → `QDRANT_URL`
4. Go to Settings, copy API Key → `QDRANT_API_KEY`

---

### LLM Providers

```bash
# Choose ONE primary provider (rest are optional fallbacks)
LLM_PROVIDER=google  # or: openai, anthropic, ollama_cloud

# Google AI (Gemini)
GOOGLE_API_KEY=...  # Get from: https://aistudio.google.com/app/apikey
# How to get: Go to Google AI Studio, create API key, copy it

# OpenAI (optional)
OPENAI_API_KEY=sk-...  # Get from: https://platform.openai.com/account/api-keys

# Anthropic (optional)
ANTHROPIC_API_KEY=sk-ant-...  # Get from: https://console.anthropic.com/account/keys
```

---

### Observability

#### Langfuse (LLM Tracing)

```bash
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

**How to get these**:
1. Go to https://us.cloud.langfuse.com (sign up if needed)
2. Create a project
3. Go to Settings > API Keys
4. Copy public key → `LANGFUSE_PUBLIC_KEY`
5. Copy secret key → `LANGFUSE_SECRET_KEY`

#### Grafana Cloud (Metrics & Tracing)

```bash
# OTLP Endpoint (São Paulo region)
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-sa-east-1.grafana.net/otlp

# Authentication header (base64 encoded)
# Format: Authorization=Basic <base64(instanceId:grafana_api_token)>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic YOUR_BASE64_CREDENTIALS
```

**How to get these**:
1. Go to https://grafana.com/auth/sign-up
2. Choose Grafana Cloud
3. Create instance in São Paulo (sa-east-1)
4. Go to Connections > Configure OTLP
5. Note your Instance ID (number)
6. Go to Account > API keys, create new token
7. Generate base64:
   ```bash
   echo -n "YOUR_INSTANCE_ID:YOUR_API_TOKEN" | base64
   # Output: YOUR_BASE64_CREDENTIALS
   ```
8. Copy to `OTEL_EXPORTER_OTLP_HEADERS`

---

### Communication & Integration

```bash
# Twilio (for SMS/WhatsApp)
TWILIO_AUTH_TOKEN=...  # Get from: https://console.twilio.com/

# SendGrid (for email) - if you use it
SENDGRID_API_KEY=...  # Get from: https://app.sendgrid.com/settings/api_keys

# LangChain (if you use LangChain agents)
LANGCHAIN_API_KEY=...
```

---

### OAuth & Security

```bash
# Google OAuth (for MCP integration)
MCP_AUTH_GOOGLE_CLIENT_ID=...
MCP_AUTH_GOOGLE_CLIENT_SECRET_DEV=...

# How to get these:
# 1. Go to https://console.cloud.google.com/
# 2. Create new project or use existing
# 3. Enable "Google+ API"
# 4. Go to Credentials → Create OAuth 2.0 Client ID
# 5. Type: Web application
# 6. Authorized redirect URIs: https://api.yourdomain.com/mcp/auth/callback
# 7. Copy Client ID and Client Secret

# Encryption key for storing user credentials (Google tokens, etc)
CREDENTIALS_ENCRYPTION_KEY=...  # Generate with:
# python -c "import secrets; print(secrets.token_hex(32))"
```

---

### Domain & Deployment

```bash
# Your domain name (for Caddy HTTPS)
DOMAIN=api.yourdomain.com

# Log level
LOG_LEVEL=INFO

# Environment marker
ENVIRONMENT=production
```

---

## 🔐 Part 2: CI/CD Secrets (for GitHub)

These go in: Settings → Secrets and variables → Actions

```
Repository Secrets:
├── REGISTRY_USERNAME
│   └── Your Docker Hub or DO username
│
├── REGISTRY_PASSWORD
│   └── Docker Hub token or DO registry token
│
├── DEPLOY_SSH_KEY
│   └── Private SSH key for Droplet (cat ~/.ssh/id_rsa)
│
├── DO_SPACES_KEY (optional)
│   └── DigitalOcean Spaces access key
│
└── DO_SPACES_SECRET (optional)
    └── DigitalOcean Spaces secret key

Repository Variables (not sensitive):
├── REGISTRY_NAMESPACE
│   └── your-username or your-org
│
├── DROPLET_IP
│   └── Your Droplet's IP address
│
└── DOCKER_BUILDKIT
    └── 1 (for faster builds)
```

---

## 📋 Validation Checklist

### Before Uploading to .env.production

- [ ] All values are actual credentials (not placeholders)
- [ ] No `<angle brackets>` or `[square brackets]`
- [ ] No comments with values
- [ ] CREDENTIALS_ENCRYPTION_KEY is 64 hex characters (32 bytes)
- [ ] QDRANT_URL and other URLs have `https://` prefix
- [ ] API keys don't have extra spaces
- [ ] Secret values are at least 20 characters
- [ ] File permissions will be: `chmod 600 .env.production`

### Before Deploying

```bash
# 1. Verify syntax (on Droplet)
cat /opt/vizu/.env.production | grep -v "^#" | grep -v "^$"

# 2. Test database connection
docker exec vizu_atendente_core python -c "
import os
from sqlalchemy import create_engine
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    print('✓ Database connected')
"

# 3. Test Qdrant connection
docker exec vizu_atendente_core python -c "
import requests
url = os.environ['QDRANT_URL']
headers = {'api-key': os.environ['QDRANT_API_KEY']}
resp = requests.get(f'{url}/health', headers=headers)
print('✓ Qdrant connected' if resp.ok else '✗ Qdrant error')
"

# 4. Check service logs
docker compose -f docker-compose.prod.yml logs atendente_core | grep -i error
```

---

## 🚨 Security Best Practices

1. **Never commit .env.production to git**
   ```bash
   # Verify in .gitignore
   grep -E "\.env\.production|\.env\.prod" .gitignore
   ```

2. **Rotate credentials regularly**
   - API keys: Every 90 days
   - Encryption keys: When policy changes
   - Database passwords: When someone leaves

3. **Limit access**
   - SSH key: Only you + CI/CD system
   - .env.production: `chmod 600` (read-only by owner)
   - GitHub Secrets: Only necessary workflows

4. **Use environment-specific values**
   - Never use production keys in .env (local dev)
   - Production `.env.production` has real keys
   - Test keys for CI/CD validation

5. **Audit logs**
   ```bash
   # View who accessed what
   sudo journalctl -u docker -f
   docker compose logs --tail=1000
   ```

---

## 🔄 Rotation Schedule

Set calendar reminders to rotate:

| Secret | Frequency | How |
|--------|-----------|-----|
| API Keys | 90 days | Regenerate in service dashboard |
| Database Password | 6 months | Via Supabase console |
| Encryption Key | Never (unless needed) | Generate new, re-encrypt |
| SSH Keys | 1 year | Generate new pair |
| OAuth Tokens | 30 days | Refresh or rotate |

---

## 🆘 If You Lose a Secret

1. **API Key (Google, OpenAI, etc.)**: Regenerate in service dashboard
2. **Database Password**: Reset via Supabase console (causes redeployment)
3. **Encryption Key**: You can't decrypt old data - migrate manually or lose it
4. **SSH Key**: Generate new pair, add to Droplet authorized_keys
5. **OAuth Secret**: Regenerate in Google Cloud Console

**Prevention**: Use a password manager (1Password, Bitwarden, etc.)

---

## Next: Generate Your .env.production

Once you have all the values, create the file:

```bash
# On your laptop first (for testing)
cp .env.production.example .env.production
nano .env.production  # Fill in all values

# Validate
source .env.production
echo "DATABASE_URL=$DATABASE_URL"  # Should show value, not placeholder

# When ready, copy to Droplet
scp .env.production vizu@<droplet-ip>:/opt/vizu/
ssh vizu@<droplet-ip> "chmod 600 /opt/vizu/.env.production"
```

Then deploy!
