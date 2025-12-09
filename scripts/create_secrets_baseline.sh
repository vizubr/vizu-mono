#!/usr/bin/env bash
set -euo pipefail

# Create a detect-secrets baseline file (.secrets.baseline).
# Usage: run this AFTER you have rotated all checked-in secrets and verified
# the repository contains only safe placeholders for keys. The script will
# generate .secrets.baseline in the repo root which you should review and
# commit. Once committed, the CI `secret-scan.yml` will enforce no *new*
# findings appear in PRs.

echo "Installing detect-secrets (quiet)..."
python -m pip install --upgrade pip >/dev/null
python -m pip install detect-secrets >/dev/null

OUT_FILE=".secrets.baseline"

echo "Scanning repository and writing baseline to $OUT_FILE"
detect-secrets scan > "$OUT_FILE"

echo "Baseline generated: $OUT_FILE"
echo "Next steps (recommended):"
echo "  1) Review the baseline: less than ideal findings may still be present."
echo "     Use: cat $OUT_FILE | detect-secrets audit -"
echo "  2) Commit and push the baseline to the repository:"
echo "     git add $OUT_FILE && git commit -m 'chore(secrets): add detect-secrets baseline' && git push"
echo "  3) After committing, CI will fail on new detect-secrets findings."

echo "If you want to exclude specific findings, run 'detect-secrets audit .secrets.baseline' and follow interactive prompts."
