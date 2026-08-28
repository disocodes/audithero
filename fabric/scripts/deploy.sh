#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="${1:-$ROOT/fabric/config/fabric.json}"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG"
  echo "Copy fabric/config/fabric.example.json to fabric/config/fabric.json and configure workspace_id."
  echo "Key Vault is optional if you will audit uploaded CSV/XLSX files."
  exit 2
fi

python -m pip install --quiet "requests>=2.32" "build>=1.2" "pyyaml>=6.0" "openpyxl>=3.1"

echo "Running AuditHero offline preflight..."
python "$ROOT/scripts/preflight.py" --platform fabric --fabric-config "$CONFIG"

echo "Deploying AuditHero core to Microsoft Fabric..."
python "$ROOT/fabric/scripts/deploy_fabric.py" --config "$CONFIG"

echo "Deploying credential-free CSV/XLSX audit path..."
python "$ROOT/fabric/scripts/deploy_file_source.py" --config "$CONFIG"

cat <<'EOF'

AuditHero Fabric deployment complete.

You can now choose either:
  A) Upload audithero_input.xlsx / canonical CSV files to Lakehouse Files/input and run
     "AuditHero - Uploaded Files Audit Pipeline" (no Employment Hero credentials required), or
  B) Configure Azure Key Vault and use the Employment Hero API pipelines.

EOF
