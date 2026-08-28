#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG="${1:-$ROOT/fabric/config/fabric.json}"
if [[ ! -f "$CONFIG" ]]; then
  echo "Create $CONFIG from fabric/config/fabric.complete.example.json"
  exit 2
fi
python -m pip install --quiet "requests>=2.32" "build>=1.2"
python "$ROOT/fabric/scripts/deploy_fabric_final.py" --config "$CONFIG"
