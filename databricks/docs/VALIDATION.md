# Databricks production validation

Before enabling the scheduled monthly job:

- run `setup` and `self_test` successfully;
- run Employment Hero connection/readiness jobs;
- resolve required mappings;
- validate representative Award cases manually;
- verify industrial-instrument history;
- test a rate boundary and June 2026 sleepover boundary;
- reconcile at least one complete known pay run;
- verify dashboard remediation totals exclude unresolved review cases;
- obtain payroll/IR sign-off.

The monthly schedule stays paused until these checks are complete.