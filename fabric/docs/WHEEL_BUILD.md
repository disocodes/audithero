# Fabric wheel build requirement

The Environment custom wheel must contain the shared `schads_audit` package plus the effective-dated SCHADS rule library. The installer invokes `fabric/scripts/build_fabric_wheel.py` and falls back to the standard project wheel build only when necessary.