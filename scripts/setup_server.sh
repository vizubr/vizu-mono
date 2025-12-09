#!/bin/bash
# ===============================================
# Vizu Production Server Setup Script
# For fresh Ubuntu 22.04+ DigitalOcean Droplet
# ===============================================
# Usage:
#   chmod +x scripts/setup_server.sh
#   ./scripts/setup_server.sh
# ===============================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (use sudo)"
    exit 1
fi

log_info "Starting Vizu server setup..."

# ===============================================
# 1. System Updates
# ===============================================
log_info "Updating system packages..."
apt-get update -y
apt-get upgrade -y

# ===============================================
# 2. Install Docker
# ===============================================
log_info "Installing Docker..."

# Remove old versions if present
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Install prerequisites
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    make

# Add Docker's official GPG key
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker
systemctl start docker
systemctl enable docker

log_info "Docker installed: $(docker --version)"
log_info "Docker Compose installed: $(docker compose version)"

# ===============================================
# 3. Create deploy user
# ===============================================
DEPLOY_USER="vizu"

if id "$DEPLOY_USER" &>/dev/null; then
    log_warn "User $DEPLOY_USER already exists"
else
    log_info "Creating deploy user: $DEPLOY_USER"
    useradd -m -s /bin/bash "$DEPLOY_USER"
    usermod -aG docker "$DEPLOY_USER"
fi

# ===============================================
# 4. Setup application directory
# ===============================================
APP_DIR="/opt/vizu"
log_info "Setting up application directory: $APP_DIR"

mkdir -p "$APP_DIR"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"

# ===============================================
# 5. Configure firewall (UFW)
# ===============================================
log_info "Configuring firewall..."

apt-get install -y ufw

ufw default deny incoming
ufw default allow outgoing

# SSH
ufw allow 22/tcp

# HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Enable firewall
ufw --force enable

log_info "Firewall configured"

# ===============================================
# 6. Configure SSH security (optional but recommended)
# ===============================================
log_info "Hardening SSH configuration..."

# Backup original config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak

# Disable password authentication (only if you have SSH keys set up!)
# Uncomment these lines if you want to disable password auth:
# sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
# sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Disable root login
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# Restart SSH
systemctl restart sshd

log_warn "SSH hardened. Make sure you have SSH key access before logging out!"

# ===============================================
# 7. Install additional tools
# ===============================================
log_info "Installing additional tools..."

apt-get install -y \
    htop \
    ncdu \
    fail2ban \
    unattended-upgrades

# Configure automatic security updates
dpkg-reconfigure -plow unattended-upgrades

# Start fail2ban
systemctl start fail2ban
systemctl enable fail2ban

# ===============================================
# 8. Setup log rotation for Docker
# ===============================================
log_info "Configuring Docker log rotation..."

cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

systemctl restart docker

# ===============================================
# Summary
# ===============================================
echo ""
echo "============================================="
log_info "Server setup complete!"
echo "============================================="
echo ""
echo "Next steps:"
echo "1. Clone your repo to $APP_DIR:"
echo "   sudo -u $DEPLOY_USER git clone https://github.com/YOUR_ORG/vizu-mono.git $APP_DIR"
echo ""
echo "2. Create .env.production file:"
echo "   sudo -u $DEPLOY_USER cp $APP_DIR/.env.production.example $APP_DIR/.env.production"
echo "   sudo -u $DEPLOY_USER nano $APP_DIR/.env.production"
echo ""
echo "3. Set your domain in Caddyfile:"
echo "   sudo -u $DEPLOY_USER nano $APP_DIR/Caddyfile"
echo ""
echo "4. Deploy the application:"
echo "   cd $APP_DIR && sudo -u $DEPLOY_USER docker compose -f docker-compose.prod.yml up -d --build"
echo ""
echo "5. View logs:"
echo "   docker compose -f docker-compose.prod.yml logs -f"
echo ""
echo "============================================="
