# Databricks compliance control registers

Databricks and Fabric require the same historical evidence. In Databricks the canonical source-controlled examples live under `config/`, and production values may be synchronized to a secured Unity Catalog Volume or bundled workspace files according to your deployment policy.

Required/optional controlled registers:

- classification mapping
- pay-category mapping
- work-type mapping
- work-location/state/local-holiday mapping
- employee overrides
- industrial-instrument history
- part-time written patterns and variations
- overtime/rest controls
- meal-break events
- supplemental events
- TOIL register
- public-holiday overrides

These files must not contain API secrets.