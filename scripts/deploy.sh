#!/usr/bin/env bash
set -euo pipefail
: "${DATABRICKS_BUNDLE_VAR_sql_warehouse_id:?Set DATABRICKS_BUNDLE_VAR_sql_warehouse_id}"
TARGET="${1:-dev}"
databricks bundle validate -t "$TARGET"
databricks bundle deploy -t "$TARGET"
databricks bundle run -t "$TARGET" setup
printf '\nDEPLOYED. NEXT: ./scripts/configure_secrets.sh, complete config mappings, then run connection_test. Monthly schedule remains PAUSED.\n'
