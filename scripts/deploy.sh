#!/usr/bin/env bash
set -euo pipefail
: "${DATABRICKS_BUNDLE_VAR_sql_warehouse_id:?Set DATABRICKS_BUNDLE_VAR_sql_warehouse_id}"
TARGET="${1:-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python -m pip install --quiet "pyyaml>=6.0"
echo "Running AuditHero offline preflight..."
python "$ROOT/scripts/preflight.py" --platform databricks

echo "Validating bundle..."
databricks bundle validate -t "$TARGET"

echo "Deploying AuditHero..."
databricks bundle deploy -t "$TARGET"

echo "Running workspace setup..."
databricks bundle run -t "$TARGET" setup

echo "Running Databricks-native regression checks..."
databricks bundle run -t "$TARGET" self_test

cat <<'EOF'

AuditHero deployed and self-tested.

NO EMPLOYMENT HERO CREDENTIALS ARE REQUIRED FOR FILE MODE.

Recommended first run:
1. Generate/fill audithero_input.xlsx or canonical CSV/XLSX files.
2. Upload them to /Volumes/schads_payroll/bronze/landing/input (or your configured catalog path).
3. Populate applicable controlled registers in config/.
4. Run: databricks bundle run manual_file_audit -- --start_date=YYYY-MM-DD --end_date=YYYY-MM-DD
5. Validate a known payroll period before running multi-year remediation.

Optional API automation:
- ./scripts/configure_secrets.sh
- databricks bundle run connection_test
- databricks bundle run audit_readiness
- then use historical_audit / monthly_audit.

The monthly API job remains PAUSED until explicitly enabled.
EOF
