#!/usr/bin/env python3
"""Create the AuditHero administration notebooks in an installed Fabric workspace."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from deploy_fabric import FabricClient, access_token

ROOT = Path(__file__).resolve().parents[2]
FABRIC = ROOT / "fabric"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(FABRIC / "config" / "fabric.json"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    client = FabricClient(cfg["workspace_id"], access_token())
    lakehouse = client.find("Lakehouse", cfg.get("lakehouse_name", "AuditHero_Lakehouse"))
    environment = client.find("Environment", cfg.get("environment_name", "AuditHero_Environment"))
    if not lakehouse or not environment:
        raise RuntimeError("AuditHero Lakehouse/Environment not found. Run the base installation first.")

    specs = {
        "AuditHero - Install or Upgrade": ROOT / "installers" / "Fabric_Install_AuditHero.py",
        "AuditHero - Uninstall": ROOT / "installers" / "Fabric_Uninstall_AuditHero.py",
    }
    for name, source_path in specs.items():
        client.upsert_notebook(
            name,
            source_path.read_text(encoding="utf-8"),
            lakehouse,
            environment,
            parameters=None,
        )
        print(f"Ready: {name}")


if __name__ == "__main__":
    main()
