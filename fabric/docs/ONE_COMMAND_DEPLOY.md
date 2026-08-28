# One-command Fabric target

The desired fresh-workspace command is:

```bash
cp fabric/config/fabric.example.json fabric/config/fabric.json
# edit workspace + Key Vault settings
./fabric/scripts/deploy.sh
```

The deployer must provision/update Lakehouse, Runtime 2.0 Environment, custom AuditHero wheel, notebooks, pipelines, disabled monthly schedule, semantic model and Power BI report; then execute setup/self-tests.