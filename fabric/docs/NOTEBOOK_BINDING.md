# Fabric notebook bindings

The REST deployer injects FabricGitSource metadata into every PySpark notebook so it is attached to the deployed AuditHero Lakehouse and Runtime 2.0 Environment. The metadata contains `default_lakehouse`, `default_lakehouse_name`, `default_lakehouse_workspace_id`, `known_lakehouses`, plus the Environment `environmentId` and `workspaceId`.