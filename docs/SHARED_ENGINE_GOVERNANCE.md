# Shared rules-engine governance

The Databricks and Fabric products must never fork Award arithmetic.

Canonical assets:

- `src/schads_audit/` — calculation modules;
- `rules/MA000100/` — effective-dated rule/rate/allowance packs;
- `tests/` — platform-independent regression tests.

Platform adapters may differ only where the platform requires it: secrets, storage/table naming, orchestration, deployment and BI.

Any rule change must include:

1. authoritative source/effective date;
2. JSON/module update;
3. regression test;
4. Databricks self-test pass;
5. Fabric self-test pass;
6. known-pay-period validation for material changes.