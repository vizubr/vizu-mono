#!/usr/bin/env bash
set -euo pipefail

# Create a detect-secrets baseline file (.secrets.baseline).
# Usage: run this AFTER you have rotated all checked-in secrets and verified
# the repository contains only safe placeholders for keys. The script will
# generate .secrets.baseline in the repo root which you should review and
# commit. Once committed, the CI `secret-scan.yml` will enforce no *new*
# findings appear in PRs.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.secrets-venv"

echo "Setting up detect-secrets environment..."

# Create a temporary venv for detect-secrets if needed
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Activate and install
source "$VENV_DIR/bin/activate"
pip install --upgrade pip >/dev/null 2>&1
pip install detect-secrets >/dev/null 2>&1

cd "$REPO_ROOT"
OUT_FILE=".secrets.baseline"

echo "Scanning repository and writing baseline to $OUT_FILE"
detect-secrets scan > "$OUT_FILE"

deactivate 2>/dev/null || true

echo "Baseline generated: $OUT_FILE"
echo "Next steps (recommended):"
echo "  1) Review the baseline: less than ideal findings may still be present."
echo "     Use: source $VENV_DIR/bin/activate && cat $OUT_FILE | detect-secrets audit -"
echo "  2) Commit and push the baseline to the repository:"
echo "     git add $OUT_FILE && git commit -m 'chore(secrets): add detect-secrets baseline' && git push"
echo "  3) After committing, CI will fail on new detect-secrets findings."

echo "If you want to exclude specific findings, run 'detect-secrets audit .secrets.baseline' and follow interactive prompts."
