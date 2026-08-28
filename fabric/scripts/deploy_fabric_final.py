#!/usr/bin/env python3
"""Final hardened AuditHero Fabric installer entrypoint."""
from __future__ import annotations
import sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path: sys.path.insert(0,str(HERE))
import deploy_fabric_complete as complete


class FinalFabricClient(complete.FabricClient):
    def update_environment(self, environment_id, environment_yml, spark_yml, wheel, wheel_name):
        super().update_environment(environment_id,environment_yml,spark_yml,wheel,wheel_name)
        deadline=time.time()+2400
        while time.time()<deadline:
            item=self.request("GET",f"/workspaces/{self.workspace_id}/environments/{environment_id}")
            state=str(((item.get('properties') or {}).get('publishDetails') or {}).get('state') or '').lower()
            if state=='success': return item
            if state in {'failed','cancelled','canceled'}:
                raise RuntimeError(f"Fabric Environment publication ended in state {state}: {item}")
            time.sleep(15)
        raise TimeoutError("Fabric Environment did not publish within 40 minutes")


complete.FabricClient=FinalFabricClient

if __name__=='__main__':
    complete.main()
