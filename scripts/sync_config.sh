#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-dev}"

python "$ROOT/scripts/bootstrap_config.py"
python "$ROOT/scripts/validate_repo.py"
python "$ROOT/scripts/databricks_preflight.py" --target "$TARGET"

echo "Deploying updated gitignored tenant configuration to Databricks target '$TARGET'..."
databricks bundle deploy -t "$TARGET"

cat <<EOF

Tenant configuration synchronized.
NEXT:
  databricks bundle run -t $TARGET audit_readiness

Repeat edit -> sync_config -> audit_readiness until blocking findings are resolved.
EOF
