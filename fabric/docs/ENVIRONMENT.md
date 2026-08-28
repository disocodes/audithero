# Fabric Environment

AuditHero targets Fabric Runtime 2.0. The Environment owns Spark/runtime configuration and the custom AuditHero wheel. Deployment publishes the Environment before invoking notebooks so production jobs do not run against stale library versions.