#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="${1:-$ROOT/fabric/config/fabric.json}"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG"
  echo "Copy fabric/config/fabric.example.json to fabric/config/fabric.json and configure workspace_id/key_vault_url."
  exit 2
fi

python -m pip install --quiet "requests>=2.32" "build>=1.2" "pyyaml>=6.0"

echo "Running AuditHero offline preflight..."
python "$ROOT/scripts/preflight.py" --platform fabric --fabric-config "$CONFIG"

echo "Deploying AuditHero to Microsoft Fabric..."
python "$ROOT/fabric/scripts/deploy_fabric.py" --config "$CONFIG"
