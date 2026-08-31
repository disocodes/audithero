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

echo "Deploying canonical CSV/XLSX audit path..."
python "$ROOT/fabric/scripts/deploy_file_source.py" --config "$CONFIG"

echo "Deploying source inspection, field mapping and conversion pipelines..."
python "$ROOT/fabric/scripts/deploy_source_mapping.py" --config "$CONFIG"

cat <<'EOF'

AuditHero Fabric deployment complete.

Normal operator path in Fabric:
  1. Upload your original payroll/HR/timekeeping exports to Lakehouse Files/import/raw.
  2. Run "AuditHero - Build Source Mapping Workbook".
  3. Review the generated Excel mapping, upload the approved version as source_mapping.xlsx.
  4. Run "AuditHero - Convert Source Files".
  5. Run "AuditHero - Uploaded Files Audit Pipeline" for the required audit period.
  6. Review the Power BI report.

If your files already use the AuditHero canonical workbook/CSV format, skip steps 2-4.
Employment Hero API connectivity is optional.
EOF
