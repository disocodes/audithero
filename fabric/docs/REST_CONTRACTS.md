# Fabric REST contracts used by installer

- `POST /v1/workspaces/{workspaceId}/lakehouses` with `creationPayload.enableSchemas=true`.
- Environment `updateDefinition` with `Libraries/CustomLibraries/*.whl`, `Libraries/PublicLibraries/environment.yml` and `Setting/Sparkcompute.yml`.
- Environment publish through `staging/publish?beta=false` during the current GA transition.
- Notebook FabricGitSource `notebook-content.py` definitions.
- Data Pipeline `pipeline-content.json` definitions with `TridentNotebook` activities.
- Core Job Scheduler `DefaultJob` schedules, monthly schedule disabled by default.