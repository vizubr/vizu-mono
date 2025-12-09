#!/usr/bin/env bash
# =============================================================================
# create_secrets.sh - Create Google Secret Manager secrets from .env file
# =============================================================================
# Usage: ./scripts/create_secrets.sh <project_id> [env_file]
#
# This script reads a .env file and creates corresponding secrets in
# Google Secret Manager. Run this once during initial setup, then use
# Cloud Run's --set-secrets to inject them at deploy time.
# =============================================================================
set -euo pipefail

PROJECT_ID="${1:-}"
ENV_FILE="${2:-.env.production}"

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: $0 <gcp_project_id> [env_file]"
    echo "Example: $0 my-project-123 .env.production"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file '$ENV_FILE' not found"
    exit 1
fi

echo "Creating secrets in project: $PROJECT_ID"
echo "Reading from: $ENV_FILE"
echo ""

# List of secret keys to create (add all your secret names here)
SECRET_KEYS=(
    "DATABASE_URL"
    "SUPABASE_URL"
    "SUPABASE_KEY"
    "SUPABASE_SERVICE_KEY"
    "SUPABASE_JWT_SECRET"
    "REDIS_URL"
    "QDRANT_URL"
    "QDRANT_API_KEY"
    "OPENAI_API_KEY"
    "ANTHROPIC_API_KEY"
    "GOOGLE_API_KEY"
    "LANGFUSE_PUBLIC_KEY"
    "LANGFUSE_SECRET_KEY"
    "DD_API_KEY"
    "CREDENTIALS_ENCRYPTION_KEY"
    "MCP_AUTH_GOOGLE_CLIENT_ID"
    "MCP_AUTH_GOOGLE_CLIENT_SECRET"
    "TWILIO_AUTH_TOKEN"
    "LANGCHAIN_API_KEY"
)

for key in "${SECRET_KEYS[@]}"; do
    # Extract value from env file (handles values with special chars)
    value=$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | sed 's/^"//' | sed 's/"$//' || true)
    
    if [ -z "$value" ] || [[ "$value" == sm://* ]] || [[ "$value" == *"<"*">"* ]]; then
        echo "⏭️  Skipping $key (empty, placeholder, or already a secret ref)"
        continue
    fi

    # Check if secret already exists
    if gcloud secrets describe "$key" --project="$PROJECT_ID" &>/dev/null; then
        echo "🔄 Updating secret: $key"
        echo -n "$value" | gcloud secrets versions add "$key" \
            --project="$PROJECT_ID" \
            --data-file=-
    else
        echo "✨ Creating secret: $key"
        echo -n "$value" | gcloud secrets create "$key" \
            --project="$PROJECT_ID" \
            --replication-policy="automatic" \
            --data-file=-
    fi
done

echo ""
echo "✅ Secret creation complete!"
echo ""
echo "Next steps:"
echo "1. Verify secrets: gcloud secrets list --project=$PROJECT_ID"
echo "2. Grant Cloud Run access:"
echo "   gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "     --member='serviceAccount:<SERVICE_ACCOUNT>@$PROJECT_ID.iam.gserviceaccount.com' \\"
echo "     --role='roles/secretmanager.secretAccessor'"
