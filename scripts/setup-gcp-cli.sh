#!/bin/bash
# ===============================================
# VIZU GCP CLI Setup
# ===============================================
# Installs and configures gcloud CLI for the team
# This is a shared development environment setup
#
# Usage:
#   ./scripts/setup-gcp-cli.sh
#
# Prerequisites:
#   - macOS or Linux (Debian/Ubuntu)
#   - Homebrew (on macOS) or apt-get (on Linux)
# ===============================================

set -e

echo "🔧 Installing Google Cloud SDK (gcloud CLI)..."

# Detect OS
OS_TYPE=$(uname -s)

if [[ "$OS_TYPE" == "Darwin" ]]; then
    # macOS
    echo "📦 Detected macOS - using Homebrew..."

    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Please install Homebrew first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi

    echo "Installing google-cloud-sdk..."
    brew install --cask google-cloud-sdk

    echo "Initializing gcloud..."
    /usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/bin/gcloud init

elif [[ "$OS_TYPE" == "Linux" ]]; then
    # Linux (Debian/Ubuntu)
    echo "📦 Detected Linux - using apt-get..."

    # Add Google Cloud SDK repo
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list > /dev/null

    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - > /dev/null

    sudo apt-get update
    echo "Installing google-cloud-sdk..."
    sudo apt-get install -y google-cloud-sdk

    echo "Initializing gcloud..."
    gcloud init

else
    echo "❌ Unsupported OS: $OS_TYPE"
    echo "Please install gcloud manually: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo ""
echo "✅ gcloud CLI installed successfully!"
echo ""
echo "📝 Next steps:"
echo "   1. Verify installation:"
echo "      gcloud --version"
echo ""
echo "   2. Authenticate with GCP:"
echo "      gcloud auth login"
echo ""
echo "   3. Set your project ID:"
echo "      gcloud config set project \$YOUR_GCP_PROJECT_ID"
echo ""
echo "   4. Verify configuration:"
echo "      gcloud config list"
echo ""
echo "For more info, see: docs/operations/CLOUD_RUN_DEPLOYMENT.md"
