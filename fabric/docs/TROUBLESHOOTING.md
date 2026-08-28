# Fabric troubleshooting

## Environment publication not complete
Wait for the Environment publish operation to reach success before executing notebooks. Notebooks bound to an unpublished Environment may use stale dependencies.

## Key Vault access denied
Verify the notebook execution identity has secret-read permission and the configured vault URL is correct.

## Employment Hero 401
Re-authorize/refresh OAuth and confirm the stored refresh token belongs to the configured client and organisation.

## Direct Lake model has missing tables
Run the BI build notebook after at least one successful audit so `gold.current_*` snapshot tables exist.

## Historical audit has many review rows
Run readiness first and resolve classification, pay-category, work-location, instrument and part-time-pattern gaps rather than weakening fail-closed behavior.

## Schedule should not run yet
The monthly schedule is intentionally disabled until validation. Enable it only after a representative pay period reconciles.