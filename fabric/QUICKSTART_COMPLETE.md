# AuditHero Fabric complete quickstart

```bash
git clone https://github.com/disocodes/audithero.git
cd audithero
git checkout complete-both-platforms
cp fabric/config/fabric.complete.example.json fabric/config/fabric.json
# edit workspace_id and key_vault_url
az login
./fabric/scripts/install-final.sh
```

Windows:

```powershell
Copy-Item fabric/config/fabric.complete.example.json fabric/config/fabric.json
# edit config
az login
./fabric/scripts/install-final.ps1
```

The installer creates/updates the schema-enabled Lakehouse, Runtime 2.0 Environment, custom AuditHero wheel, bound notebooks, historical/monthly pipelines, disabled monthly schedule, setup/self-test and Direct Lake/Power BI layer.

Then:

1. populate Azure Key Vault Employment Hero secrets;
2. run **AuditHero - Employment Hero Connection**;
3. run **AuditHero - Readiness**;
4. resolve Lakehouse `Files/config` mappings/control registers;
5. run one known historical pay period;
6. run your three-year historical range;
7. review Power BI;
8. set `monthly_schedule_enabled=true` and redeploy only after acceptance.