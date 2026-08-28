#!/usr/bin/env bash
set -euo pipefail
SCOPE="${1:-audithero}"

command -v databricks >/dev/null 2>&1 || { echo "Databricks CLI is required."; exit 2; }
databricks current-user me >/dev/null 2>&1 || {
  echo "Databricks authentication failed. Run 'databricks auth login --host https://<workspace>'."
  exit 2
}

databricks secrets create-scope "$SCOPE" 2>/dev/null || true

put_required() {
  local key="$1" value=""
  while [[ -z "$value" ]]; do
    read -rsp "Enter $key: " value
    echo
    [[ -n "$value" ]] || echo "Value is required."
  done
  databricks secrets put-secret "$SCOPE" "$key" --string-value "$value"
  unset value
  echo "✓ $key"
}

put_optional() {
  local key="$1" value=""
  read -rsp "Enter $key (blank to skip): " value
  echo
  if [[ -z "$value" ]]; then
    echo "Skipped $key"
    return
  fi
  databricks secrets put-secret "$SCOPE" "$key" --string-value "$value"
  unset value
  echo "✓ $key"
}

put_required EH_ORGANISATION_ID
put_required EH_HR_CLIENT_ID
put_required EH_HR_CLIENT_SECRET
put_required EH_HR_REFRESH_TOKEN

read -rp "Configure Employment Hero Payroll API for actual-pay reconciliation? [Y/n] " Y
Y="${Y:-Y}"
if [[ "${Y,,}" == "y" ]]; then
  put_required EH_PAYROLL_API_KEY
  put_required EH_PAYROLL_BUSINESS_ID
else
  put_optional EH_PAYROLL_API_KEY
  put_optional EH_PAYROLL_BUSINESS_ID
fi

cat <<EOF

Databricks secret scope '$SCOPE' is configured.
NEXT: complete config mappings/registers, then run:
  databricks bundle run connection_test
  databricks bundle run audit_readiness
EOF
