#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="${1:-$ROOT/fabric/config/fabric.json}"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG"
  echo "Copy fabric/config/fabric.example.json to fabric/config/fabric.json first."
  exit 2
fi
command -v az >/dev/null 2>&1 || { echo "Azure CLI (az) is required."; exit 2; }
az account show >/dev/null 2>&1 || { echo "Run 'az login' first."; exit 2; }

VAULT_NAME="$(python - "$CONFIG" <<'PY'
import json,re,sys
cfg=json.load(open(sys.argv[1],encoding='utf-8'))
url=str(cfg.get('key_vault_url','')).strip()
m=re.fullmatch(r'https://([A-Za-z0-9-]+)\.vault\.azure\.net/?',url)
if not m: raise SystemExit('Invalid key_vault_url in fabric config')
print(m.group(1))
PY
)"
ACTUAL_SOURCE="$(python - "$CONFIG" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1],encoding='utf-8'))
print(str(cfg.get('historical_defaults',{}).get('actual_pay_source','PAYROLL_API')).upper())
PY
)"

echo "Configuring canonical AuditHero secrets in Azure Key Vault: $VAULT_NAME"

put_secret() {
  local name="$1"
  local optional="${2:-false}"
  local value=""
  if [[ "$optional" == "true" ]]; then
    read -rsp "Enter $name (blank to skip): " value
  else
    while [[ -z "$value" ]]; do
      read -rsp "Enter $name: " value
      [[ -n "$value" ]] || echo -e "\nValue is required."
    done
  fi
  echo
  if [[ -z "$value" ]]; then
    echo "Skipped $name"
    return
  fi
  az keyvault secret set \
    --vault-name "$VAULT_NAME" \
    --name "$name" \
    --value "$value" \
    --output none
  unset value
  echo "✓ $name"
}

put_secret EH-ORGANISATION-ID
put_secret EH-HR-CLIENT-ID
put_secret EH-HR-CLIENT-SECRET
put_secret EH-HR-REFRESH-TOKEN

if [[ "$ACTUAL_SOURCE" == "PAYROLL_API" ]]; then
  echo "Employment Hero Payroll reconciliation is enabled in the Fabric config."
  put_secret EH-PAYROLL-API-KEY
  put_secret EH-PAYROLL-BUSINESS-ID
else
  echo "actual_pay_source=$ACTUAL_SOURCE; payroll API secrets are not required."
  put_secret EH-PAYROLL-API-KEY true
  put_secret EH-PAYROLL-BUSINESS-ID true
fi

cat <<EOF

Key Vault values are configured.

NEXT:
1. Ensure the Fabric notebook execution identity has Key Vault secret-read permission.
2. Run:
     python fabric/scripts/preflight.py --config "$CONFIG" --check-secrets
3. Deploy:
     ./fabric/scripts/deploy.sh "$CONFIG"

Secret values were not written to Git or local config files.
EOF
