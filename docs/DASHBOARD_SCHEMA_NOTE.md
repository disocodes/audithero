# Dashboard schema qualification

Databricks dashboard datasets that read non-gold tables must use two-part schema qualification (`ops.audit_runs`, `ref.rule_coverage`) because the dashboard's default schema is `gold`.