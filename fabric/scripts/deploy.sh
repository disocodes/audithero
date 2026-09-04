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

echo "Deploying automatic and advanced uploaded-file audit paths..."
python "$ROOT/fabric/scripts/deploy_file_source.py" --config "$CONFIG"

echo "Deploying advanced source inspection, field mapping and conversion pipelines..."
python "$ROOT/fabric/scripts/deploy_source_mapping.py" --config "$CONFIG"

echo "Deploying AuditHero administration notebooks..."
python "$ROOT/fabric/scripts/deploy_admin_notebooks.py" --config "$CONFIG"

cat <<'EOF'

AuditHero Fabric deployment complete.

Primary operator path in Fabric:
  1. Upload ordinary timesheet, employee, rate-history and optional payroll CSV/XLSX files to Lakehouse Files/import/raw.
  2. Run "AuditHero - Auto Audit Uploaded Files".
  3. Open the AuditHero Power BI report.
  4. Select the employee, SCHADS stream, level, pay point and employment type as required to review Award scenarios and detailed findings.

AuditHero automatically aligns effective-dated employee rates to shift dates, calculates supported SCHADS penalties/overtime/rest/break/sleepover/broken-shift/minimum-engagement outcomes, and identifies unresolved evidence as review findings rather than blocking the rest of the audit.

Advanced import tools remain available for unusual source layouts:
  - AuditHero - Build Source Mapping Workbook
  - AuditHero - Convert Source Files
  - AuditHero - Convert Mapped Files and Run Audit
  - AuditHero - Canonical Files Audit (Advanced)

Administration notebooks:
  - AuditHero - Install or Upgrade
  - AuditHero - Uninstall

Employment Hero API connectivity is optional.
EOF
