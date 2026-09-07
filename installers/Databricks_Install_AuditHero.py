# Databricks notebook source
# MAGIC %md
# MAGIC # AuditHero — Install or Upgrade
# MAGIC
# MAGIC Production installer for AuditHero on Databricks. **Run all** updates the application release, ensures Jobs and workspace resources are configured, runs environment Setup, deploys/verifies the AI/BI dashboard, runs a synthetic SCHADS calculation Self Test, and writes an installation report.
# MAGIC
# MAGIC Setup, Dashboard deployment and Self Test are deliberately separate phases. **A failed phase raises an exception in its own cell**, so Databricks shows the cell as failed instead of displaying a misleading green success tick. Because the phases are separate, an operator can inspect/fix the failed phase and then manually run later diagnostic cells when appropriate.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Installer dependencies
# MAGIC Installs only the packages needed by this installer to call Databricks APIs, download the selected release, and read AuditHero's resource manifest.
# COMMAND ----------
# MAGIC %pip install -q "databricks-sdk>=0.20" "pyyaml>=6.0" "requests>=2.32"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Installation settings
# MAGIC Existing resources are reused where possible. Leave `sql_warehouse_id` blank to reuse an available warehouse or create **AuditHero SQL Warehouse** when permitted.
# COMMAND ----------
release_ref = "main"
catalog = "schads_payroll"
install_root = "/Shared/AuditHero"
sql_warehouse_id = ""
create_sql_warehouse_if_missing = True
secret_scope = "audithero"
monthly_cron = "0 0 9 25 * ?"
timezone = "Australia/Perth"
existing_cluster_id = ""
INSTALLER_BUILD = "2026-09-08-production-phases-v6"
DASHBOARD_BUILD = "2026-09-08-simulator-v4"
DASHBOARD_NAME = "AuditHero - SCHADS Payroll Compliance"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Connect to this Databricks workspace
# MAGIC All installation actions use the identity running this notebook.
# COMMAND ----------
import base64, importlib.util, json, tempfile, time, zipfile
from pathlib import Path
import requests, yaml
from databricks.sdk import WorkspaceClient
w = WorkspaceClient(); api = w.api_client; me = w.current_user.me()
accounts_email = getattr(me, "user_name", None) or getattr(me, "userName", None) or ""
print(f"User: {accounts_email}\nWorkspace: {w.config.host}\nRelease: {release_ref}\nInstaller build: {INSTALLER_BUILD}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Download and validate the selected AuditHero release
# MAGIC The release is downloaded before the workspace is changed. Required production setup, dashboard, simulation, Self Test and Job definitions must all be present.
# COMMAND ----------
archive_url = f"https://api.github.com/repos/disocodes/audithero/zipball/{release_ref}"
work_dir = Path(tempfile.mkdtemp(prefix="audithero-install-")); archive_path = work_dir / "audithero.zip"
r = requests.get(archive_url, timeout=180); r.raise_for_status(); archive_path.write_bytes(r.content)
with zipfile.ZipFile(archive_path) as zf: zf.extractall(work_dir / "source")
roots = [p for p in (work_dir / "source").iterdir() if p.is_dir()]
if len(roots) != 1: raise RuntimeError("AuditHero release archive did not contain one repository root.")
repo_root = roots[0]
required = [
    "notebooks/00_setup.py", "notebooks/00c_setup_genie.py", "notebooks/00d_verify_dashboard.py",
    "notebooks/00e_setup_investigation_view.py", "notebooks/00f_setup_pay_simulation.py",
    "notebooks/00g_setup_pay_review_master.py", "notebooks/01b_self_test.py", "notebooks/02f_auto_intake.py",
    "dashboard/payroll_compliance.spec.json", "dashboard/lakeview_builder.py", "dashboard/dashboard_enhancements.py",
    "dashboard/pay_simulation_dashboard.py", "dashboard/live_pay_simulator.py",
    "dashboard/live_pay_simulator_finalize.py", "dashboard/dashboard_layout_finalize.py", "resources/jobs.yml",
]
missing = [x for x in required if not (repo_root / x).exists()]
if missing: raise RuntimeError("Selected AuditHero release is incomplete: " + ", ".join(missing))
print(f"Release downloaded and validated: {repo_root.name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Workspace helpers
# MAGIC Shared API/import helpers used by the remaining installation phases.
# COMMAND ----------
def call(method, path, body=None, query=None): return api.do(method, path, body=body, query=query)
def mkdirs(path): call("POST", "/api/2.0/workspace/mkdirs", {"path": path})
def import_file(local, target, notebook=False):
    call("POST", "/api/2.0/workspace/import", {
        "path": target, "format": "SOURCE" if notebook else "RAW",
        **({"language": "PYTHON"} if notebook else {}),
        "content": base64.b64encode(local.read_bytes()).decode("ascii"), "overwrite": True,
    })
def list_dashboards():
    out=[]; token=None
    while True:
        q={"page_size":100}; q.update({"page_token":token} if token else {})
        p=call("GET","/api/2.0/lakeview/dashboards",query=q) or {}; out += p.get("dashboards",[]) or p.get("value",[]) or []
        token=p.get("next_page_token") or p.get("nextPageToken")
        if not token: return out
def load_module(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    if s is None or s.loader is None: raise RuntimeError(f"Cannot load AuditHero module: {path}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def canonical(v):
    if isinstance(v,str): v=json.loads(v)
    return json.dumps(v,sort_keys=True,separators=(",",":"))
mkdirs(install_root)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Install or upgrade AuditHero workspace files and notebooks
# MAGIC Installs source code, rules, configuration and dashboard definitions under `/Shared/AuditHero`, then imports executable notebooks and administration notebooks. Existing workspace copies are upgraded in place.
# COMMAND ----------
for name in ("databricks.yml","pyproject.toml","README.md"):
    p=repo_root/name
    if p.exists(): import_file(p,f"{install_root}/{name}")
for directory in ("src","rules","config","dashboard"):
    base=repo_root/directory
    if not base.exists(): continue
    for p in base.rglob("*"):
        if p.is_file():
            rel=p.relative_to(repo_root).as_posix(); dest=f"{install_root}/{rel}"
            mkdirs(str(Path(dest).parent).replace("\\","/")); import_file(p,dest)
mkdirs(f"{install_root}/notebooks")
for p in sorted((repo_root/"notebooks").glob("*.py")):
    import_file(p,f"{install_root}/notebooks/{p.name if p.name=='_common.py' else p.stem}",notebook=p.name!="_common.py")
mkdirs(f"{install_root}/admin")
import_file(repo_root/"installers/Databricks_Install_AuditHero.py",f"{install_root}/admin/AuditHero - Install or Upgrade",True)
import_file(repo_root/"installers/Databricks_Uninstall_AuditHero.py",f"{install_root}/admin/AuditHero - Uninstall",True)
print("Workspace files and notebooks installed/upgraded.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. Resolve the SQL warehouse
# MAGIC Reuses an existing warehouse whenever possible. A warehouse is required for AI/BI dashboards, dashboard refreshes and Genie.
# COMMAND ----------
def warehouses(): return (call("GET","/api/2.0/sql/warehouses") or {}).get("warehouses",[]) or []
def resolve_warehouse(requested):
    if requested.strip(): return requested.strip(),False
    ws=warehouses(); preferred=next((x for x in ws if x.get("name")=="AuditHero SQL Warehouse"),None)
    chosen=preferred or next((x for x in ws if x.get("state")=="RUNNING"),None) or (ws[0] if ws else None)
    if chosen: return chosen["id"],False
    if not create_sql_warehouse_if_missing: raise RuntimeError("No SQL warehouse available.")
    created=call("POST","/api/2.0/sql/warehouses",{"name":"AuditHero SQL Warehouse","cluster_size":"2X-Small","min_num_clusters":1,"max_num_clusters":1,"auto_stop_mins":10,"enable_photon":True,"warehouse_type":"PRO","enable_serverless_compute":True})
    return created["id"],True
warehouse_id, warehouse_created_by_installer = resolve_warehouse(sql_warehouse_id)
print(f"SQL warehouse: {warehouse_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 8. Resolve the managed dashboard ID
# MAGIC Existing dashboards are not downgraded here. On first install only, a base dashboard is created so Job definitions have a dashboard ID. The fully enhanced dashboard is published later in its own phase.
# COMMAND ----------
matches=[d for d in list_dashboards() if d.get("display_name")==DASHBOARD_NAME]
if matches:
    dashboard_id=matches[0]["dashboard_id"]; print(f"Using existing dashboard ID: {dashboard_id}")
else:
    b=load_module("audithero_placeholder",repo_root/"dashboard/lakeview_builder.py")
    spec=json.loads((repo_root/"dashboard/payroll_compliance.spec.json").read_text())
    created=call("POST","/api/2.0/lakeview/dashboards",{"display_name":DASHBOARD_NAME,"warehouse_id":warehouse_id,"serialized_dashboard":b.build_dashboard_text(spec),"parent_path":install_root},query={"dataset_catalog":catalog,"dataset_schema":"gold"})
    dashboard_id=created["dashboard_id"]
    call("POST",f"/api/2.0/lakeview/dashboards/{dashboard_id}/published",{"embed_credentials":False,"warehouse_id":warehouse_id})
    print(f"Created first-install dashboard placeholder: {dashboard_id}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 9. Create or update AuditHero Jobs
# MAGIC Installs the complete production Job set from `resources/jobs.yml`: Setup, Self Test, uploaded-file workflows, rate confirmation, advanced mapping, optional Employment Hero API workflows, historical audit and the paused monthly schedule. Existing Jobs are reset in place instead of duplicated.
# COMMAND ----------
jobs_doc=yaml.safe_load((repo_root/"resources/jobs.yml").read_text()); job_defs=jobs_doc["resources"]["jobs"]
repl={"${var.catalog}":catalog,"${var.secret_scope}":secret_scope,"${var.sql_warehouse_id}":warehouse_id,"${var.accounts_email}":accounts_email,"${var.monthly_cron}":monthly_cron,"${var.timezone}":timezone,"${resources.dashboards.payroll_compliance.id}":dashboard_id}
def resolve(v):
    if isinstance(v,dict):
        out={k:resolve(x) for k,x in v.items()}
        if existing_cluster_id and "notebook_task" in out and "existing_cluster_id" not in out: out["existing_cluster_id"]=existing_cluster_id
        return out
    if isinstance(v,list): return [resolve(x) for x in v]
    if not isinstance(v,str): return v
    if v.startswith("../notebooks/"): return f"{install_root}/notebooks/{Path(v).stem}"
    for a,b in repl.items(): v=v.replace(a,str(b))
    return v
def list_jobs():
    out=[]; token=None
    while True:
        q={"limit":100}; q.update({"page_token":token} if token else {}); p=call("GET","/api/2.2/jobs/list",query=q) or {}; out+=p.get("jobs",[]) or []
        token=p.get("next_page_token")
        if not token:return out
existing_by_name={j.get("settings",{}).get("name"):j for j in list_jobs()}; installed_jobs={}
legacy={"AuditHero - Build Source Mapping Workbook (Advanced)":"AuditHero - Build Source Mapping Workbook","AuditHero - Convert Source Files (Advanced)":"AuditHero - Convert Source Files","AuditHero - Convert Mapped Files and Run Audit (Advanced)":"AuditHero - Convert Mapped Files and Run Audit","AuditHero - File Readiness (Advanced)":"AuditHero - File Readiness","AuditHero - Audit Canonical CSV Excel (Advanced)":"AuditHero - Audit Uploaded CSV Excel"}
for key,raw in job_defs.items():
    settings=resolve(raw); name=settings["name"]; existing=existing_by_name.get(name) or existing_by_name.get(legacy.get(name,""))
    if existing:
        call("POST","/api/2.2/jobs/reset",{"job_id":existing["job_id"],"new_settings":settings}); job_id=existing["job_id"]; print(f"Updated job: {name}")
    else:
        job_id=call("POST","/api/2.2/jobs/create",settings)["job_id"]; print(f"Created job: {name}")
    installed_jobs[key]=job_id

# COMMAND ----------
# MAGIC %md
# MAGIC ## 10. Job execution and error diagnostics
# MAGIC Setup and Self Test run in separate cells. For a multi-task Job, the diagnostics distinguish the **actual failed task** from tasks that were merely blocked/skipped because an upstream dependency failed.
# COMMAND ----------
def get_run(run_id): return call("GET","/api/2.2/jobs/runs/get",query={"run_id":run_id}) or {}
def run_output(run_id):
    for ver in ("2.2","2.1"):
        try:return call("GET",f"/api/{ver}/jobs/runs/get-output",query={"run_id":run_id}) or {}
        except Exception:pass
    return {}
def diagnostics(parent_id):
    tasks=get_run(parent_id).get("tasks",[]) or []
    actual=[]; blocked=[]
    for t in tasks:
        s=t.get("state",{}) or {}; result=s.get("result_state"); lifecycle=s.get("life_cycle_state")
        if result=="SUCCESS": continue
        row=(t,s)
        if lifecycle=="SKIPPED" or result=="UPSTREAM_FAILED": blocked.append(row)
        else: actual.append(row)
    for heading,rows in (("FAILED TASK",actual),("BLOCKED TASK",blocked)):
        for t,s in rows:
            key=t.get("task_key","unknown"); rid=t.get("run_id")
            print(f"\n{heading}: {key} | run={rid} | lifecycle={s.get('life_cycle_state')} | result={s.get('result_state')}")
            if s.get("state_message"): print("  "+s["state_message"])
            if rid and heading=="FAILED TASK":
                o=run_output(rid); text=o.get("error") or o.get("error_trace") or (o.get("notebook_output") or {}).get("result")
                if text: print(str(text)[:12000])
    return {
        "failed_tasks":[t.get("task_key","unknown") for t,_ in actual],
        "blocked_tasks":[t.get("task_key","unknown") for t,_ in blocked],
    }
def run_job(job_id,label,timeout=3600):
    rid=call("POST","/api/2.2/jobs/run-now",{"job_id":job_id})["run_id"]; print(f"Started {label}: run {rid}"); deadline=time.time()+timeout
    while time.time()<deadline:
        s=get_run(rid).get("state",{}) or {}; lifecycle=s.get("life_cycle_state"); result=s.get("result_state")
        if lifecycle in {"TERMINATED","SKIPPED","INTERNAL_ERROR"}:
            ok=result=="SUCCESS"
            diag={"failed_tasks":[],"blocked_tasks":[]} if ok else diagnostics(rid)
            obj={"ok":ok,"run_id":rid,"lifecycle":lifecycle,"result":result,"message":s.get("state_message") or "",**diag}
            print(f"{label}: {'SUCCESS' if ok else 'FAILED'}")
            return obj
        time.sleep(10)
    return {"ok":False,"run_id":rid,"lifecycle":"TIMEOUT","result":None,"message":f"Timed out after {timeout}s","failed_tasks":[],"blocked_tasks":[]}
def require_success(result,label):
    if result["ok"]: return
    root=", ".join(result.get("failed_tasks") or []) or "unknown task"
    blocked=", ".join(result.get("blocked_tasks") or [])
    detail=f"; blocked downstream tasks: {blocked}" if blocked else ""
    raise RuntimeError(
        f"{label} failed. Root failed task(s): {root}{detail}. "
        f"Open Databricks Job run {result['run_id']} for the full notebook output."
    )

# COMMAND ----------
# MAGIC %md
# MAGIC ## 11. Run AuditHero environment Setup
# MAGIC **This is the production environment/resource phase, not the calculation Self Test.** The Setup Job has independent task boundaries so failures are attributable:
# MAGIC
# MAGIC - `setup` — core Unity Catalog objects, persistent Delta tables, schema migrations, SCHADS reference rules and core reporting/metric views;
# MAGIC - `setup_genie` — create/update the managed Genie space;
# MAGIC - `setup_investigation_view` — employee/shift investigation reporting view;
# MAGIC - `setup_pay_simulation` — roster-pay simulation tables/views;
# MAGIC - `setup_pay_review_master` — employee/year review master;
# MAGIC - `verify_dashboard` — validates the dashboard definition and required views, but does not publish it.
# MAGIC
# MAGIC A failure in this cell **raises an exception after diagnostics are printed**, so the cell must appear red in Databricks. Downstream cells remain separate and can be run manually for diagnostics after the failed Setup issue is understood.
# COMMAND ----------
setup_result=run_job(installed_jobs["setup"],"AuditHero Setup"); setup_run_id=setup_result["run_id"]
require_success(setup_result,"AuditHero Setup")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 12. Dashboard data preflight
# MAGIC Checks the governed views required by the managed AI/BI dashboard. Missing views are a real deployment error and this cell raises instead of printing a false success state.
# COMMAND ----------
view_names=["v_audit_investigation_latest","v_award_scenario_detail_latest","v_award_criteria_detail_latest","v_award_scenario_rest_findings_latest","v_reconciliation_latest","v_audit_runs","v_readiness_findings","v_rule_coverage","v_pay_review_employee_master","v_pay_simulation_terms_latest","v_pay_simulation_employee_year"]
dashboard_missing_views=[]
for v in view_names:
    try:spark.sql(f"SELECT 1 FROM `{catalog}`.`gold`.`{v}` LIMIT 1").collect()
    except Exception as exc:dashboard_missing_views.append((f"{catalog}.gold.{v}",str(exc)))
if dashboard_missing_views:
    print("Dashboard preflight FAILED:")
    for n,e in dashboard_missing_views: print(f"  - {n}: {e[:1000]}")
    raise RuntimeError("AuditHero dashboard preflight failed; required governed views are missing or not queryable: "+", ".join(n for n,_ in dashboard_missing_views))
print("Dashboard preflight PASSED: all required views are queryable.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 13. Build, publish and verify the enhanced AI/BI dashboard
# MAGIC Applies the version-controlled dashboard enhancements, roster-pay simulator and current 12-column layout; verifies the simulator controls and page width; then updates/publishes every managed dashboard with the AuditHero dashboard name. A publication/verification failure raises in this cell.
# COMMAND ----------
verified_dashboard_ids=[]; dashboard_result={"ok":False,"status":"NOT_RUN","message":""}
try:
    builder=load_module("builder",repo_root/"dashboard/lakeview_builder.py"); enh=load_module("enh",repo_root/"dashboard/dashboard_enhancements.py"); pay=load_module("pay",repo_root/"dashboard/pay_simulation_dashboard.py"); sim=load_module("sim",repo_root/"dashboard/live_pay_simulator.py"); fin=load_module("fin",repo_root/"dashboard/live_pay_simulator_finalize.py")
    spec=json.loads((repo_root/"dashboard/payroll_compliance.spec.json").read_text()); spec=fin.enhance_spec(sim.enhance_spec(pay.enhance_spec(enh.enhance_spec(spec))))
    final_json=builder.build_dashboard(spec); final_text=json.dumps(final_json,separators=(",",":"))
    names={x.get("widget",{}).get("name") for p in final_json.get("pages",[]) for x in p.get("layout",[])}
    needed={"live_sim_title","sim_year","sim_scenario","sim_exact_rate","sim_pay_model","sim_selected_rate_kpi","sim_total","sim_variance","sim_summary_heading","sim_pay_outcomes_heading","sim_shift_calculations_heading","sim_award_components_heading","sim_shift_table","sim_component_table"}
    miss=sorted(needed-names)
    if miss:raise RuntimeError("Dashboard missing simulator widgets: "+", ".join(miss))
    page=next((p for p in final_json.get("pages",[]) if p.get("name")=="employee_deep_dive"),None)
    if not page:raise RuntimeError("Dashboard has no Employee Deep Dive page")
    extent=max((x.get("position",{}).get("x",0)+x.get("position",{}).get("width",0) for x in page.get("layout",[])),default=0)
    if extent<12:raise RuntimeError(f"Employee Deep Dive is not full-width; extent={extent}")
    targets=[d for d in list_dashboards() if d.get("display_name")==DASHBOARD_NAME]
    if not targets:raise RuntimeError("Managed AuditHero dashboard was not found")
    for d in targets:
        tid=d["dashboard_id"]; cur=call("GET",f"/api/2.0/lakeview/dashboards/{tid}") or {}; body={"dashboard_id":tid,"display_name":DASHBOARD_NAME,"warehouse_id":warehouse_id,"serialized_dashboard":final_text}
        if cur.get("etag"):body["etag"]=cur["etag"]
        call("PATCH",f"/api/2.0/lakeview/dashboards/{tid}",body,query={"dataset_catalog":catalog,"dataset_schema":"gold"})
        stored=call("GET",f"/api/2.0/lakeview/dashboards/{tid}") or {}
        if canonical(stored.get("serialized_dashboard") or "{}")!=canonical(final_text):raise RuntimeError(f"Databricks did not retain enhanced dashboard {tid}")
        call("POST",f"/api/2.0/lakeview/dashboards/{tid}/published",{"embed_credentials":False,"warehouse_id":warehouse_id}); verified_dashboard_ids.append(tid)
        print(f"Enhanced dashboard verified: {tid}; dashboard_build={DASHBOARD_BUILD}")
    dashboard_id=verified_dashboard_ids[0]; dashboard_result={"ok":True,"status":"SUCCESS","message":f"Verified {len(verified_dashboard_ids)} dashboard(s)"}
except Exception as exc:
    dashboard_result={"ok":False,"status":"FAILED","message":str(exc)}
    print("Dashboard deployment FAILED:\n"+str(exc))
    raise RuntimeError("AuditHero dashboard deployment failed: "+str(exc)) from exc

# COMMAND ----------
# MAGIC %md
# MAGIC ## 14. Deployment checkpoint before Self Test
# MAGIC At this point Setup and Dashboard deployment must both have passed. This checkpoint is informational only.
# COMMAND ----------
print(f"Setup: PASS (run {setup_run_id})")
print(f"Dashboard: PASS ({dashboard_result['status']}) — {dashboard_result.get('message','')}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 15. Run AuditHero Self Test — second-last phase
# MAGIC **Self Test uses synthetic data only; it does not read your employee/payroll files.** It checks deterministic calculation-engine behaviour:
# MAGIC
# MAGIC 1. SCHADS rule-library integrity and effective-dated 2024/2026 SACS rates.
# MAGIC 2. A four-hour casual Saturday penalty calculation against a known expected amount.
# MAGIC 3. Sleepover treatment: sleepover span is not ordinary worked hours and allowance evidence is produced.
# MAGIC 4. Local public-holiday scoping: a local holiday applies only to the matching location key.
# MAGIC 5. Broken-shift grouping and broken-shift allowance evidence.
# MAGIC 6. Weekly/period overtime threshold allocation and repricing evidence.
# MAGIC
# MAGIC A failure means the installed code/rule runtime does not reproduce these synthetic examples. It is **not** a test of Employment Hero connectivity, uploaded source-file quality, dashboard permissions, or whether any real employee is compliant. A failed Self Test raises in this cell.
# COMMAND ----------
self_test_result=run_job(installed_jobs["self_test"],"AuditHero Self Test"); self_test_run_id=self_test_result["run_id"]
require_success(self_test_result,"AuditHero Self Test")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 16. Save installation report and declare final production status
# MAGIC Reached only after Setup, Dashboard and Self Test have succeeded during **Run all**. Saves release/resource IDs to `/Shared/AuditHero/install_state.json` and prints the operator workflow.
# COMMAND ----------
state={"release_ref":release_ref,"installer_build":INSTALLER_BUILD,"dashboard_build":DASHBOARD_BUILD,"catalog":catalog,"install_root":install_root,"warehouse_id":warehouse_id,"warehouse_created_by_installer":warehouse_created_by_installer,"dashboard_id":dashboard_id,"dashboard_ids_verified":verified_dashboard_ids,"setup":setup_result,"dashboard":dashboard_result,"self_test":self_test_result,"setup_run_id":setup_run_id,"self_test_run_id":self_test_run_id,"jobs":installed_jobs,"installed_by":accounts_email}
call("POST","/api/2.0/workspace/import",{"path":f"{install_root}/install_state.json","format":"RAW","content":base64.b64encode(json.dumps(state,indent=2).encode()).decode("ascii"),"overwrite":True})
print("\nAUDITHERO INSTALL / UPGRADE SUMMARY")
print("  Setup:     PASS")
print("  Dashboard: PASS")
print("  Self Test: PASS")
print("AuditHero installation completed successfully.")
print("Employee Deep Dive should begin with Roster Pay Simulator and use the full 12-column canvas.")
print("Primary uploaded-file workflow:")
print("  1. Upload ordinary CSV/XLSX files to the raw import folder")
print("  2. Run AuditHero - Preview Uploaded Files")
print("  3. Review/confirm interpretation, then run AuditHero - Audit Reviewed Uploaded Files")
print("  4. Open AuditHero - SCHADS Payroll Compliance")
