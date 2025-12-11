#!/bin/bash
# ===============================================
# Vizu Deployment Script
# Run this on the server after setup
# ===============================================
# Usage:
#   ./scripts/deploy.sh [pull|build|restart|logs|status]
# ===============================================

set -euo pipefail

# Configuration
APP_DIR="/opt/vizu"
COMPOSE_FILE="docker-compose.prod.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

cd "$APP_DIR" || { log_error "Cannot cd to $APP_DIR"; exit 1; }

# Check for .env.production
check_env() {
    if [ ! -f ".env.production" ]; then
        log_error ".env.production not found!"
        log_info "Copy from example: cp .env.production.example .env.production"
        exit 1
    fi
}

# Pull latest code
pull() {
    log_step "Pulling latest code from git..."
    git pull origin main
}

# Build containers
build() {
    check_env
    log_step "Building containers..."
    docker compose -f "$COMPOSE_FILE" build --parallel
}

# Start/restart services
start() {
    check_env
    log_step "Starting services..."
    docker compose -f "$COMPOSE_FILE" up -d
}

# Stop services
stop() {
    log_step "Stopping services..."
    docker compose -f "$COMPOSE_FILE" down
}

# Restart services
restart() {
    check_env
    log_step "Restarting services..."
    docker compose -f "$COMPOSE_FILE" down
    docker compose -f "$COMPOSE_FILE" up -d
}

# View logs
logs() {
    local service="${1:-}"
    if [ -n "$service" ]; then
        docker compose -f "$COMPOSE_FILE" logs -f "$service"
    else
        docker compose -f "$COMPOSE_FILE" logs -f
    fi
}

# Check status
status() {
    log_step "Service status:"
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    log_step "Resource usage:"
    docker stats --no-stream
}

# Health check
health() {
    log_step "Running health checks..."

    services=(
        "atendente_core:8000"
        "tool_pool_api:9000"
        "analytics_api:8000"
        "embedding_service:11435"
        "vendas_agent:8000"
        "support_agent:8000"
    )

    for svc in "${services[@]}"; do
        name="${svc%%:*}"
        port="${svc##*:}"

        # Use docker exec to check from inside the network
        if docker exec "vizu_${name}" curl -sf "http://localhost:${port}/health" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name"
        fi
    done
}

# Full deployment (pull, build, restart)
deploy() {
    pull
    build
    restart
    log_info "Waiting for services to start..."
    sleep 30
    health
}

# Cleanup unused resources
cleanup() {
    log_step "Cleaning up unused Docker resources..."
    docker system prune -f
    docker image prune -f
}

# Show help
help() {
    echo "Vizu Deployment Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  deploy    - Full deployment (pull, build, restart)"
    echo "  pull      - Pull latest code"
    echo "  build     - Build containers"
    echo "  start     - Start services"
    echo "  stop      - Stop services"
    echo "  restart   - Restart services"
    echo "  logs      - View logs (optionally: logs <service>)"
    echo "  status    - Show service status"
    echo "  health    - Run health checks"
    echo "  cleanup   - Clean unused Docker resources"
    echo ""
}

# Main
case "${1:-help}" in
    deploy)  deploy ;;
    pull)    pull ;;
    build)   build ;;
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    logs)    logs "${2:-}" ;;
    status)  status ;;
    health)  health ;;
    cleanup) cleanup ;;
    help|*)  help ;;
esac
