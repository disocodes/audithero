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

echo "Deploying source inspection, field mapping and conversion/audit pipelines..."
python "$ROOT/fabric/scripts/deploy_source_mapping.py" --config "$CONFIG"

cat <<'EOF'

AuditHero Fabric deployment complete.

Normal operator path in Fabric:
  1. Upload original payroll/HR/rostering/timekeeping exports to Lakehouse Files/import/raw.
  2. Run "AuditHero - Build Source Mapping Workbook".
  3. Review the generated Excel mapping and upload the approved version as source_mapping.xlsx.
  4. Run "AuditHero - Convert Mapped Files and Run Audit" for the required dates.
  5. Review the Power BI report.

Use "AuditHero - Convert Source Files" when you only want to test conversion/readiness.
If files already use the AuditHero canonical workbook/CSV format, upload them to Files/input and run the direct uploaded-file audit pipeline.
Employment Hero API connectivity is optional.
EOF
