#!/usr/bin/env bash
set -euo pipefail

# Install detect-secrets and run a JSON scan. This script intentionally
# does not cause CI to fail; it writes the findings to `artifacts/detect-secrets.json`
# so maintainers can review and create a baseline after rotating secrets.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OUT_DIR="$REPO_ROOT/artifacts"
mkdir -p "$OUT_DIR"

# Use venv on local (macOS / externally managed Python) or pip directly in CI
if [ -n "${CI:-}" ]; then
    # CI environment: pip install directly (GitHub Actions runners allow this)
    python3 -m pip install --upgrade pip >/dev/null 2>&1
    python3 -m pip install detect-secrets >/dev/null 2>&1
    DETECT_SECRETS_CMD="detect-secrets"
else
    # Local environment: use a dedicated venv
    VENV_DIR="${REPO_ROOT}/.secrets-venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip >/dev/null 2>&1
    pip install detect-secrets >/dev/null 2>&1
    DETECT_SECRETS_CMD="detect-secrets"
fi

cd "$REPO_ROOT"
echo "Running detect-secrets scan..."
$DETECT_SECRETS_CMD scan --json > "$OUT_DIR/detect-secrets.json" || true

echo "Summary of findings:"
python3 - <<'PY'
import json,sys
f='artifacts/detect-secrets.json'
try:
    data=json.load(open(f))
except Exception as e:
    print('No results file found or parse error:', e)
    sys.exit(0)

secrets = data.get('results', {})
count = sum(len(v) for v in secrets.values())
print(f"  Total findings: {count}")
for filename, issues in list(secrets.items())[:10]:
    print(f"  {filename}: {len(issues)}")
    for it in issues[:3]:
        print('    -', it.get('type'), 'line', it.get('line_number'))

PY

# Deactivate venv if we activated one
if [ -z "${CI:-}" ]; then
    deactivate 2>/dev/null || true
fi

echo "Detect-secrets scan complete; results in $OUT_DIR/detect-secrets.json"
