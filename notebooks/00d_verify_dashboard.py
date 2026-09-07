# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Validate AI/BI Dashboard
# MAGIC
# MAGIC **Purpose:** validate that the complete AuditHero dashboard can be built from the
# MAGIC installed release and that all governed reporting/simulation views required by
# MAGIC the dashboard exist.
# MAGIC
# MAGIC This Setup task deliberately **does not publish or update Lakeview dashboards**.
# MAGIC The interactive **AuditHero - Install or Upgrade** notebook is the single dashboard
# MAGIC publisher. Keeping publication in one place avoids job-runtime permission/auth
# MAGIC differences and prevents Setup from hiding a useful Lakeview API error behind a
# MAGIC generic Workload failed message.
# COMMAND ----------
from pathlib import Path
import importlib.util
import json

exec(open(str(Path.cwd() / "_common.py")).read())

# COMMAND ----------
dbutils.widgets.text("catalog", "schads_payroll")
dbutils.widgets.text("sql_warehouse_id", "")

catalog = dbutils.widgets.get("catalog").strip() or "schads_payroll"
warehouse_id = dbutils.widgets.get("sql_warehouse_id").strip()
if not warehouse_id:
    raise ValueError("sql_warehouse_id is required to validate the AuditHero dashboard")

DASHBOARD_BUILD = "2026-09-08-simulator-v4"

paths = {
    "spec": ROOT / "dashboard" / "payroll_compliance.spec.json",
    "builder": ROOT / "dashboard" / "lakeview_builder.py",
    "enhancements": ROOT / "dashboard" / "dashboard_enhancements.py",
    "pay_review": ROOT / "dashboard" / "pay_simulation_dashboard.py",
    "simulator": ROOT / "dashboard" / "live_pay_simulator.py",
    "finalizer": ROOT / "dashboard" / "live_pay_simulator_finalize.py",
    "layout": ROOT / "dashboard" / "dashboard_layout_finalize.py",
}
missing_files = [str(path) for path in paths.values() if not path.exists()]
if missing_files:
    raise FileNotFoundError("AuditHero dashboard component(s) missing: " + ", ".join(missing_files))


def _load_module(name: str, path: Path):
    module_spec = importlib.util.spec_from_file_location(name, path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"AuditHero dashboard module could not be loaded: {path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


# These are created by Setup immediately before this task. There is no legacy/core
# fallback in this release: if a simulation view is missing, fail with its name.
required_views = [
    "v_audit_investigation_latest",
    "v_award_scenario_detail_latest",
    "v_award_criteria_detail_latest",
    "v_award_scenario_rest_findings_latest",
    "v_reconciliation_latest",
    "v_audit_runs",
    "v_readiness_findings",
    "v_rule_coverage",
    "v_pay_review_employee_master",
    "v_pay_simulation_terms_latest",
    "v_pay_simulation_employee_year",
]
missing_views = []
for view in required_views:
    full_name = f"`{catalog}`.`gold`.`{view}`"
    try:
        spark.sql(f"SELECT 1 FROM {full_name} LIMIT 1").collect()
    except Exception as exc:
        print(f"Required dashboard view failed: {catalog}.gold.{view}: {type(exc).__name__}: {exc}")
        missing_views.append(f"{catalog}.gold.{view}")
if missing_views:
    raise RuntimeError(
        "AuditHero dashboard validation cannot continue because Setup did not create required view(s): "
        + ", ".join(missing_views)
    )

builder = _load_module("audithero_lakeview_builder", paths["builder"])
enhancements = _load_module("audithero_dashboard_enhancements", paths["enhancements"])
pay_review = _load_module("audithero_pay_simulation_dashboard", paths["pay_review"])
simulator = _load_module("audithero_live_pay_simulator", paths["simulator"])
finalizer = _load_module("audithero_live_pay_simulator_finalize", paths["finalizer"])

spec = json.loads(paths["spec"].read_text(encoding="utf-8"))
spec = enhancements.enhance_spec(spec)
spec = pay_review.enhance_spec(spec)
spec = simulator.enhance_spec(spec)
spec = finalizer.enhance_spec(spec)

desired_json = builder.build_dashboard(spec)

if not desired_json.get("datasets"):
    raise ValueError("AuditHero dashboard definition contains no datasets")
if not desired_json.get("pages"):
    raise ValueError("AuditHero dashboard definition contains no pages")
if len(desired_json["pages"]) > 15:
    raise ValueError(f"AuditHero dashboard exceeds Databricks page limit: {len(desired_json['pages'])}")

for dataset in desired_json["datasets"]:
    if not isinstance(dataset.get("queryLines"), list) or not dataset.get("queryLines"):
        raise ValueError(f"Dashboard dataset {dataset.get('name')} has no queryLines")
    for parameter in dataset.get("parameters", []) or []:
        for key in ("keyword", "displayName", "dataType", "defaultSelection"):
            if key not in parameter or parameter.get(key) in (None, ""):
                raise ValueError(
                    f"Dashboard parameter {dataset.get('name')}.{parameter.get('keyword')} is missing {key}"
                )

all_layout = [item for page in desired_json["pages"] for item in page.get("layout", [])]
widget_names = {item.get("widget", {}).get("name") for item in all_layout}
required_widgets = {
    "live_sim_title",
    "sim_year",
    "sim_scenario",
    "sim_exact_rate",
    "sim_pay_model",
    "sim_selected_rate_kpi",
    "sim_total",
    "sim_variance",
    "sim_summary_heading",
    "sim_pay_outcomes_heading",
    "sim_shift_calculations_heading",
    "sim_award_components_heading",
    "sim_shift_table",
    "sim_component_table",
}
missing_widgets = sorted(required_widgets - widget_names)
if missing_widgets:
    raise RuntimeError("Generated AuditHero dashboard is missing simulator widgets: " + ", ".join(missing_widgets))

employee_page = next((p for p in desired_json["pages"] if p.get("name") == "employee_deep_dive"), None)
if employee_page is None:
    raise RuntimeError("Generated AuditHero dashboard has no Employee Deep Dive page")

live_title = next(
    (item for item in employee_page.get("layout", []) if item.get("widget", {}).get("name") == "live_sim_title"),
    None,
)
if live_title is None or live_title.get("position", {}).get("y") != 0:
    raise RuntimeError("Roster Pay Simulator is not positioned at the top of Employee Deep Dive")

employee_extent = max(
    (
        item.get("position", {}).get("x", 0) + item.get("position", {}).get("width", 0)
        for item in employee_page.get("layout", [])
    ),
    default=0,
)
if employee_extent < 12:
    raise RuntimeError(
        f"Employee Deep Dive does not fill the current 12-column Databricks canvas; extent={employee_extent}"
    )

print(f"AuditHero dashboard definition validated successfully; build={DASHBOARD_BUILD}")
print(f"Datasets: {len(desired_json['datasets'])}; pages: {len(desired_json['pages'])}; widgets: {len(all_layout)}")
print("Roster Pay Simulator is at the top of Employee Deep Dive and the page spans 12 columns.")
print("Lakeview publication is intentionally deferred to AuditHero - Install or Upgrade.")
