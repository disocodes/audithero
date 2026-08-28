#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${DATABRICKS_BUNDLE_VAR_sql_warehouse_id:?Set DATABRICKS_BUNDLE_VAR_sql_warehouse_id}"
TARGET="${1:-dev}"

echo "Creating safe empty tenant configuration files where missing..."
python "$ROOT/scripts/bootstrap_config.py"

echo "Running repository preflight..."
python "$ROOT/scripts/validate_repo.py"

echo "Running Databricks authentication/warehouse preflight..."
python "$ROOT/scripts/databricks_preflight.py" --target "$TARGET"

echo "Validating Databricks bundle..."
databricks bundle validate -t "$TARGET"

echo "Deploying AuditHero..."
databricks bundle deploy -t "$TARGET"

echo "Running workspace setup..."
databricks bundle run -t "$TARGET" setup

echo "Running Databricks-native regression checks..."
databricks bundle run -t "$TARGET" self_test

cat <<EOF

AuditHero deployed and self-tested.

NEXT:
1. ./scripts/configure_secrets.sh
2. databricks bundle run -t $TARGET connection_test
3. databricks bundle run -t $TARGET audit_readiness
4. Populate the local config/*.json and controlled CSV registers identified by readiness.
5. ./scripts/sync_config.sh $TARGET
6. Rerun audit_readiness until blocking findings are resolved.
7. Run a one-month historical validation sample.
8. Only then run the full multi-year audit and enable the monthly schedule.

The monthly job remains PAUSED until you explicitly enable it.
EOF
