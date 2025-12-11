# Production Deployment Guide - DigitalOcean

This document covers deploying Vizu services to a DigitalOcean Droplet using Docker Compose with automatic HTTPS via Caddy.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DigitalOcean Droplet                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      Docker Network                          │ │
│  │                                                              │ │
│  │   ┌─────────┐      ┌──────────────────┐                     │ │
│  │   │  Caddy  │──────│  atendente_core  │                     │ │
│  │   │  :80    │      │  :8000           │                     │ │
│  │   │  :443   │──────│  tool_pool_api   │                     │ │
│  │   └─────────┘      │  :9000           │                     │ │
│  │        │           │  ...other svcs   │                     │ │
│  │        │           └──────────────────┘                     │ │
│  │        │                    │                                │ │
│  │        │           ┌────────┴────────┐                      │ │
│  │        │           │ embedding_svc   │                      │ │
│  │        │           │ :11435          │                      │ │
│  │        │           └─────────────────┘                      │ │
│  └────────┴─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
           │                    │                     │
           ▼                    ▼                     ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │   Supabase   │    │ Qdrant Cloud │    │Grafana Cloud │
    │   (DB)       │    │  (Vector)    │    │  (OTLP)      │
    └──────────────┘    └──────────────┘    └──────────────┘
```

## Prerequisites

1. **DigitalOcean Account** with a Droplet (Ubuntu 22.04+)
   - Recommended: 4GB RAM / 2 vCPUs minimum
   - 8GB RAM / 4 vCPUs for production traffic

2. **Domain Name** pointing to your Droplet IP
   - Configure DNS A record: `api.yourdomain.com` → `<droplet-ip>`

3. **External Services** (already configured):
   - Supabase project (database)
   - Qdrant Cloud cluster (vector search)
   - Grafana Cloud account (observability)
   - Langfuse account (LLM tracing)

## Quick Start

### 1. Create a Droplet

```bash
# Via doctl CLI (optional)
doctl compute droplet create vizu-prod \
  --size s-2vcpu-4gb \
  --image ubuntu-22-04-x64 \
  --region nyc1 \
  --ssh-keys <your-ssh-key-fingerprint>
```

Or use the DigitalOcean Console to create a Droplet.

### 2. Initial Server Setup

SSH into your Droplet and run the setup script:

```bash
ssh root@<droplet-ip>

# Clone the repo temporarily to get the setup script
git clone https://github.com/YOUR_ORG/vizu-mono.git /tmp/vizu-setup
chmod +x /tmp/vizu-setup/scripts/setup_server.sh
/tmp/vizu-setup/scripts/setup_server.sh

# Clean up
rm -rf /tmp/vizu-setup
```

The setup script will:
- Install Docker and Docker Compose
- Create a `vizu` deploy user
- Configure firewall (UFW)
- Set up automatic security updates
- Configure Docker log rotation

### 3. Deploy the Application

```bash
# Switch to vizu user
sudo -u vizu -i

# Clone the repository
git clone https://github.com/YOUR_ORG/vizu-mono.git /opt/vizu
cd /opt/vizu

# Create production environment file
cp .env.production.example .env.production
nano .env.production  # Fill in your secrets

# Configure your domain in Caddyfile
nano Caddyfile  # Replace YOUR_DOMAIN with your actual domain

# Build and start services
docker compose -f docker-compose.prod.yml up -d --build

# Check status
docker compose -f docker-compose.prod.yml ps
```

### 4. Verify Deployment

```bash
# Check service health
./scripts/deploy.sh health

# View logs
./scripts/deploy.sh logs

# Check specific service
docker compose -f docker-compose.prod.yml logs -f atendente_core
```

## Configuration

### Environment Variables

Copy `.env.production.example` to `.env.production` and fill in:

```bash
# Database (Supabase)
DATABASE_URL=postgresql://postgres.[ref]:[pass]@...
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Vector DB (Qdrant Cloud)
QDRANT_URL=https://xxx.cloud.qdrant.io:6333
QDRANT_API_KEY=...

# LLM Provider
LLM_PROVIDER=google
GOOGLE_API_KEY=...

# Observability
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# Grafana OTLP (generate base64: echo -n "instanceId:apiKey" | base64)
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-sa-east-1.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64>

# Domain
DOMAIN=api.yourdomain.com
```

### Caddy Configuration

Edit `Caddyfile` to set your domain:

```caddyfile
api.yourdomain.com {
    handle /chat* {
        reverse_proxy atendente_core:8000
    }
    # ... rest of config
}
```

Caddy will automatically obtain and renew Let's Encrypt certificates.

## Operations

### Deployment Script

Use `scripts/deploy.sh` for common operations:

```bash
# Full deployment (pull, build, restart)
./scripts/deploy.sh deploy

# Just pull latest code
./scripts/deploy.sh pull

# Build containers
./scripts/deploy.sh build

# Restart services
./scripts/deploy.sh restart

# View all logs
./scripts/deploy.sh logs

# View specific service logs
./scripts/deploy.sh logs atendente_core

# Check status
./scripts/deploy.sh status

# Health check all services
./scripts/deploy.sh health

# Clean up unused Docker resources
./scripts/deploy.sh cleanup
```

### Manual Docker Commands

```bash
cd /opt/vizu

# Start services
docker compose -f docker-compose.prod.yml up -d

# Stop services
docker compose -f docker-compose.prod.yml down

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Rebuild single service
docker compose -f docker-compose.prod.yml up -d --build atendente_core

# Shell into container
docker exec -it vizu_atendente_core /bin/bash

# View resource usage
docker stats
```

### Updating the Application

```bash
cd /opt/vizu

# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# Or use the deploy script
./scripts/deploy.sh deploy
```

## Monitoring

### Grafana Cloud

Traces and metrics are sent to Grafana Cloud via OTLP:

1. Log into Grafana Cloud
2. Go to Explore → Select your datasource
3. Query by service: `service.name="vizu-prod"`

### Langfuse

LLM traces are sent to Langfuse:

1. Log into Langfuse
2. View traces under your project
3. Filter by session, user, or model

### Server Monitoring

```bash
# Resource usage
htop

# Disk usage
df -h
ncdu /opt/vizu

# Docker logs
docker compose -f docker-compose.prod.yml logs --tail=100

# System logs
journalctl -u docker -f
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs <service-name>

# Check if port is in use
sudo lsof -i :<port>

# Verify environment
docker compose -f docker-compose.prod.yml config
```

### SSL Certificate Issues

Caddy handles SSL automatically. If issues:

```bash
# Check Caddy logs
docker compose -f docker-compose.prod.yml logs caddy

# Verify DNS resolution
dig api.yourdomain.com

# Ensure ports 80/443 are open
sudo ufw status
```

### Out of Memory

```bash
# Check memory usage
free -h
docker stats

# Increase swap (temporary)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Database Connection Issues

```bash
# Test connection from container
docker exec vizu_atendente_core python -c "
import os
from sqlalchemy import create_engine
engine = create_engine(os.environ['DATABASE_URL'])
conn = engine.connect()
print('Connected!')
conn.close()
"
```

## Security Checklist

- [ ] SSH keys configured, password auth disabled
- [ ] Firewall (UFW) enabled, only 22/80/443 open
- [ ] `.env.production` has correct permissions (`chmod 600`)
- [ ] Fail2ban running
- [ ] Automatic security updates enabled
- [ ] HTTPS working (Caddy auto-provisioned)
- [ ] No secrets in git history

## Backup & Recovery

### Database

Supabase handles backups automatically. For manual backup:

```bash
# Export via Supabase Dashboard
# Or use pg_dump with your connection string
```

### Application Data

```bash
# Backup HuggingFace cache (optional)
docker run --rm -v vizu_huggingface_cache:/data -v $(pwd):/backup \
  alpine tar cvf /backup/hf-cache-backup.tar /data
```

## Scaling

### Vertical Scaling

Resize your Droplet via DigitalOcean Console:
1. Power off Droplet
2. Resize to larger plan
3. Power on

### Horizontal Scaling (Future)

For high availability, consider:
- Multiple Droplets behind a Load Balancer
- DigitalOcean Kubernetes (DOKS)
- Managed database (Supabase already handles this)
