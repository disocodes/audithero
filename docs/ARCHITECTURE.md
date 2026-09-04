# AuditHero architecture and code guide

AuditHero separates source evidence, interpretation, canonical normalization, readiness, SCHADS calculation, audit persistence and reporting. This separation allows source layouts to change without changing Award formulas and allows evidence gaps to be surfaced independently of calculation logic.

```text
Original CSV/XLSX exports                  Optional Employment Hero API
          |                                           |
          v                                           v
 Preview / automatic intake                    API extraction
          |                                           |
          |-- interpretation acceptable               |
          |          |                                |
          |          v                                |
          |   prepared canonical data                 |
          |                                           |
          |-- correction required                     |
                     |                                |
                     v                                |
          Advanced Mapping / Context                  |
                     |                                |
                     v                                |
               canonical conversion                  |
                     \                                /
                      \                              /
                       v                            v
                        Canonical AuditHero evidence
                                   |
                         normalization / readiness
                                   |
                                   v
                       Shared SCHADS audit engine
                                   |
                      effective-dated MA000100 packs
                                   |
                    +--------------+--------------+
                    |              |              |
              definitive detail  controls      reconciliation
                    |              |              |
                    +--------------+--------------+
                                   |
                            traceable audit run
                                   |
                 +-----------------+-----------------+
                 |                                   |
          Microsoft Fabric                       Databricks
                 |                                   |
      Lakehouse + Direct Lake                Silver/Gold Delta
                 |                                   |
              Power BI                    metric views / AI/BI / Genie
```

## Source evidence and interpretation

Original source files are retained as evidence. Interpretation does not rewrite them.

`src/schads_audit/auto_intake.py` handles the standard CSV/XLSX path. It uses conservative header recognition to identify usable timesheets, employee/rate attributes and clearly structured payroll earning lines. Unknown employment types, work groups, classifications and industrial instruments remain unknown.

Automatic intake produces:

- canonical candidate datasets;
- per-file interpretation metadata;
- source-field mappings used for the automatic interpretation;
- audit-window metadata derived from usable shifts; and
- review warnings.

The Databricks and Fabric preview notebooks publish this interpretation as `auto_intake_preview.csv` and publish `auto_intake_manifest.json` beside prepared canonical files.

## Advanced Mapping / Context

`src/schads_audit/source_mapping.py` provides source scanning, draft mapping and controlled conversion primitives.

`src/schads_audit/source_mapping_hardening.py` applies stricter recognition rules for payroll earning lines and rejects optional numeric mappings whose sampled values are not predominantly numeric.

`src/schads_audit/mapping_workbook.py` creates and reads the Excel correction/context workbook. Important controls include:

- controlled dropdown lists backed by uploaded file/sheet/column inventory;
- explicit canonical dataset roles;
- `CONTEXT_ONLY` and `IGNORE` handling;
- one-primary-source-per-dataset validation;
- controlled value translation; and
- no execution of arbitrary workbook formulas or Python expressions.

The workbook changes interpretation only. `mapping_used.json` records the approved mapping used for conversion.

## Canonical evidence model

`src/schads_audit/file_source.py` defines the canonical file datasets and loads CSV/XLSX evidence.

The core calculation datasets are:

- `employees`
- `pay_details`
- `employment_history`
- `timesheets`

Additional canonical evidence can include:

- `rostered_shifts`
- `payroll_earnings`
- `pay_runs`
- `industrial_instrument_history`
- `part_time_patterns`
- `part_time_variations`
- `public_holiday_overrides`
- `overtime_rest_controls`
- `meal_break_events`
- `supplemental_events`
- `toil_register`
- `pay_category_mapping`

## Canonical normalization

`src/schads_audit/canonical_normalization.py` converts canonical date/time and numeric fields while retaining `_invalid_<field>` flags where a populated source value cannot be converted. Invalid evidence therefore remains visible to readiness rather than being silently converted to an apparently valid blank or zero.

## Readiness

`src/schads_audit/file_readiness.py` evaluates whether canonical evidence is suitable for the requested audit workflow. It validates:

- required datasets and columns;
- populated required values;
- invalid canonical types;
- parseable required temporal evidence;
- shift interval ordering;
- employee/timesheet key uniqueness;
- employee referential integrity;
- classification evidence;
- pay-period evidence;
- industrial-instrument controls;
- part-time pattern controls;
- work-group/state context; and
- payroll/pay-category reconciliation readiness.

Readiness is intentionally stricter than file parsing. A file may be readable but not audit-ready.

## Calculation engine

`src/schads_audit/engine.py` performs shift-level entitlement calculation from supplied employee, employment, classification, shift, holiday and rule evidence. It fails closed when a required classification/rate/condition fact cannot be established.

The calculation path is extended by dedicated modules, including:

- `roster_overtime.py` — rostered and period overtime controls;
- `broken_sleepover.py` — broken-shift and sleepover calculations;
- `rest_breaks.py` — rest-between-work controls;
- `part_time_patterns.py` — part-time pattern/variation checks;
- `rest_meal.py` — meal-break controls;
- `industrial_instruments.py` — Award/EA/IFA/salary coverage controls;
- `supplemental.py` — controlled supplemental events; and
- `toil.py` — TOIL evidence and outcomes.

`src/schads_audit/manual_audit.py` orchestrates the complete file-based audit using these modules.

## Award scenarios

`src/schads_audit/award_scenarios.py` recalculates supplied shifts across supported SCHADS classification families, work groups and employment types. Scenario outputs are analytical comparators. They do not establish the employee's legal classification, industrial instrument or employment status.

## Actual-pay reconciliation

Actual-pay reconciliation is separate from entitlement calculation. A supplied base rate is not treated as proof of complete actual pay.

`manual_audit.py` enables actual-pay reconciliation only when payroll earnings contain the required identifying fields and a controlled pay-category treatment mapping is available. Missing payroll amounts remain null rather than being converted to zero.

## Rule library

`src/schads_audit/rules.py` loads the manifest and effective-dated rate, condition and allowance packs under `rules/MA000100`.

Rule selection uses the latest eligible pack with `operative_date <= reference_date`. For rates, the selected pack must also contain the requested classification code. If no eligible rule exists, the engine does not extrapolate a rate.

`rules/MA000100/manifest.json` is the authoritative inventory of bundled rule-pack coverage.

## Platform orchestration

### Databricks

Primary orchestration is defined in `resources/jobs.yml`.

Standard file jobs:

1. `AuditHero - Preview Uploaded Files`
2. `AuditHero - Audit Reviewed Uploaded Files`

Advanced jobs provide mapping generation, conversion, canonical readiness and mapped/canonical audits.

API historical/monthly notebooks use `src/schads_audit/databricks_pipeline_v2.py` and persist normalized evidence to Silver, calculations to Gold and run metadata to `ops`.

`src/schads_audit/databricks_io.py` creates governed result views and metric views used by AI/BI and Genie.

### Microsoft Fabric

Fabric file pipelines are deployed by `fabric/scripts/deploy_file_source.py` as separate preview and reviewed-audit pipelines. Advanced mapping pipelines are deployed separately.

`src/schads_audit/fabric_pipeline.py` is the API audit orchestration path. Fabric persists source/evidence and Gold results in the Lakehouse and publishes current successful snapshots for Direct Lake reporting.

## Audit run integrity

Persisted calculation outputs include `audit_run_id` and audit-window metadata. Reporting views/snapshots use successful audit runs. A failed or incomplete run must not replace the current successful reporting state.

## Status integrity

`REQUIRES_REVIEW` is deliberately separate from `UNDERPAID` and `OVERPAID`. Review findings indicate that a material fact or control is unresolved; they are not confirmed remediation amounts.

`ACTUAL_PAY_UNAVAILABLE` / `ENTITLEMENT_ONLY` indicates that supported expected entitlement analysis is available without sufficient evidence for a definitive actual-versus-expected comparison.

## Extension rules

Production extensions should preserve these boundaries:

1. source adapters normalize evidence but do not embed Award formulas;
2. source mapping must not infer legal classifications or coverage without evidence;
3. Award logic belongs in effective-dated rule packs and calculation modules;
4. missing evidence remains null/review rather than becoming a default factual assertion;
5. reporting consumes calculated results and does not recreate payroll formulas; and
6. new platform-specific orchestration should call the shared package rather than fork calculation logic.
