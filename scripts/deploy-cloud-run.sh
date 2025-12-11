#!/bin/bash
# Deploy Vizu to Google Cloud Run
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - GCP_PROJECT_ID set in environment
#   - GCP_REGION set (default: us-east1)

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-east1}"
REGISTRY="us-east1-docker.pkg.dev"
SERVICE_ACCOUNT="${GCP_SA_EMAIL:-github-actions@${PROJECT_ID}.iam.gserviceaccount.com}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Validate prerequisites
validate_prerequisites() {
    log "Validating prerequisites..."

    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI not found. Please install it: https://cloud.google.com/sdk/docs/install"
    fi

    if ! command -v docker &> /dev/null; then
        error "Docker not found. Please install it: https://docs.docker.com/get-docker/"
    fi

    if [ -z "$PROJECT_ID" ]; then
        error "GCP_PROJECT_ID not set. Export it: export GCP_PROJECT_ID=your-project"
    fi

    log "Prerequisites validated ✓"
}

# Configure Docker for Artifact Registry
configure_docker() {
    log "Configuring Docker for Artifact Registry..."
    gcloud auth configure-docker ${REGISTRY}
    log "Docker configured ✓"
}

# Create Artifact Registry repository if not exists
create_registry() {
    log "Ensuring Artifact Registry repository exists..."

    if ! gcloud artifacts repositories describe vizu \
        --location=${REGION} \
        --project=${PROJECT_ID} &> /dev/null; then
        log "Creating Artifact Registry repository..."
        gcloud artifacts repositories create vizu \
            --repository-format=docker \
            --location=${REGION} \
            --project=${PROJECT_ID}
        log "Repository created ✓"
    else
        log "Repository already exists ✓"
    fi
}

# Build and push a single service
build_and_push() {
    local service=$1
    local dockerfile=$2
    local pythonpath=$3

    log "Building $service..."

    local image_uri="${REGISTRY}/${PROJECT_ID}/vizu/${service}:$(date +%Y%m%d-%H%M%S)-$(git rev-parse --short HEAD)"

    docker build \
        --build-arg PYTHONPATH="${pythonpath}" \
        -t "${image_uri}" \
        -f "${dockerfile}" .

    log "Pushing $service to Artifact Registry..."
    docker push "${image_uri}"

    log "$service built and pushed ✓"
    echo "${image_uri}"
}

# Deploy a service to Cloud Run
deploy_to_cloud_run() {
    local service_name=$1
    local image_uri=$2
    local memory=$3
    local cpu=$4
    local concurrency=$5
    local timeout=$6
    local max_instances=$7
    local min_instances=$8
    local port=${9:-8000}
    local allow_unauthenticated=${10:-true}

    log "Deploying $service_name to Cloud Run..."

    local allow_flag=""
    if [ "$allow_unauthenticated" = "true" ]; then
        allow_flag="--allow-unauthenticated"
    else
        allow_flag="--no-allow-unauthenticated"
    fi

    gcloud run deploy "${service_name}" \
        --image="${image_uri}" \
        --region=${REGION} \
        --platform=managed \
        ${allow_flag} \
        --memory="${memory}" \
        --cpu="${cpu}" \
        --concurrency="${concurrency}" \
        --timeout="${timeout}" \
        --max-instances="${max_instances}" \
        --min-instances="${min_instances}" \
        --port="${port}" \
        --ingress=internal-and-cloud-load-balancing \
        --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO" \
        --service-account="${SERVICE_ACCOUNT}" \
        --project=${PROJECT_ID} \
        --quiet

    log "$service_name deployed ✓"
}

# Main deployment
main() {
    local deploy_type=${1:-all}

    validate_prerequisites
    configure_docker
    create_registry

    case "$deploy_type" in
        agents-pool)
            log "Deploying agents pool..."

            # Atendente Core (main entry point)
            local img=$(build_and_push "atendente-core" \
                "services/atendente_core/Dockerfile" \
                "/app/services/atendente_core/src")
            deploy_to_cloud_run "atendente-core" "$img" "2Gi" "2" "10" "3600" "50" "1"

            # Tool Pool API
            local img=$(build_and_push "tool-pool-api" \
                "services/tool_pool_api/Dockerfile" \
                "/app/services/tool_pool_api/src")
            deploy_to_cloud_run "tool-pool-api" "$img" "2Gi" "2" "5" "3600" "20" "1" "9000" "false"

            # Vendas Agent
            local img=$(build_and_push "vendas-agent" \
                "services/vendas_agent/Dockerfile" \
                "/app/src")
            deploy_to_cloud_run "vendas-agent" "$img" "2Gi" "2" "10" "3600" "50" "0"

            # Support Agent
            local img=$(build_and_push "support-agent" \
                "services/support_agent/Dockerfile" \
                "/app/src")
            deploy_to_cloud_run "support-agent" "$img" "2Gi" "2" "10" "3600" "50" "0"
            ;;

        workers-pool)
            log "Deploying workers pool..."

            # Data Ingestion Worker
            local img=$(build_and_push "data-ingestion-worker" \
                "services/data_ingestion_worker/Dockerfile" \
                "/app/src:/app/libs")
            deploy_to_cloud_run "data-ingestion-worker" "$img" "1Gi" "2" "50" "600" "100" "0" "8000" "false"

            # File Processing Worker
            local img=$(build_and_push "file-processing-worker" \
                "services/file_processing_worker/Dockerfile" \
                "/app/src")
            deploy_to_cloud_run "file-processing-worker" "$img" "2Gi" "2" "20" "1800" "50" "0" "8000" "false"

            # File Upload API
            local img=$(build_and_push "file-upload-api" \
                "services/file_upload_api/Dockerfile" \
                "/app/src")
            deploy_to_cloud_run "file-upload-api" "$img" "1Gi" "2" "50" "300" "50" "1"
            ;;

        embedding-service)
            log "Deploying embedding service..."
            local img=$(build_and_push "embedding-service" \
                "services/embedding_service/Dockerfile" \
                "/app/src")
            deploy_to_cloud_run "embedding-service" "$img" "2Gi" "2" "50" "60" "50" "1" "11435" "false"
            ;;

        all)
            log "Deploying all services..."
            $0 agents-pool
            $0 workers-pool
            $0 embedding-service
            ;;

        *)
            error "Unknown service: $deploy_type. Options: agents-pool, workers-pool, embedding-service, all"
            ;;
    esac

    log "Deployment complete ✓"
}

# Run main if script is executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
