#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${DATABRICKS_BUNDLE_VAR_sql_warehouse_id:?Set DATABRICKS_BUNDLE_VAR_sql_warehouse_id}"
TARGET="${1:-dev}"

echo "Running repository preflight..."
python "$ROOT/scripts/validate_repo.py"

echo "Validating Databricks bundle..."
databricks bundle validate -t "$TARGET"

echo "Deploying AuditHero..."
databricks bundle deploy -t "$TARGET"

echo "Running workspace setup..."
databricks bundle run -t "$TARGET" setup

echo "Running Databricks-native regression checks..."
databricks bundle run -t "$TARGET" self_test

cat <<'EOF'

AuditHero deployed and self-tested.

NEXT:
1. ./scripts/configure_secrets.sh
2. Complete config mappings and controlled historical registers.
3. databricks bundle run -t dev connection_test
4. databricks bundle run -t dev audit_readiness
5. Run a one-month historical validation sample.
6. Only then run the full multi-year audit and enable the monthly schedule.

The monthly job remains PAUSED until you explicitly enable it.
EOF
