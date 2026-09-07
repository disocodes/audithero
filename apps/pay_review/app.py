from __future__ import annotations

from io import BytesIO
import math
import os
import uuid

import numpy as np
import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

CATALOG = os.getenv("AUDITHERO_CATALOG", "schads_payroll")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "")

st.set_page_config(page_title="AuditHero Pay Review", page_icon="📊", layout="wide")


@st.cache_resource
def _config():
    return Config()


def _connection():
    cfg = _config()
    if not WAREHOUSE_ID:
        raise RuntimeError("WAREHOUSE_ID is not configured. Bind the AuditHero app to a Databricks SQL warehouse.")
    server_hostname = str(cfg.host).replace("https://", "").replace("http://", "").rstrip("/")
    return sql.connect(
        server_hostname=server_hostname,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


def query_df(statement: str, parameters=None) -> pd.DataFrame:
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters or [])
            if cursor.description is None:
                return pd.DataFrame()
            return cursor.fetchall_arrow().to_pandas()


def execute(statement: str, parameters=None) -> None:
    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters or [])


def current_user() -> str:
    try:
        headers = st.context.headers
        return (
            headers.get("x-forwarded-email")
            or headers.get("x-forwarded-preferred-username")
            or headers.get("x-forwarded-user")
            or "unknown"
        )
    except Exception:
        return "local-user"


def money(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"${float(value):,.2f}"


def simulate(row: pd.Series, rate: float, model: str) -> float:
    fixed = float(row.get("fixed_award_amount") or 0)
    if model == "FLAT_LOADED_HOURLY":
        return float(row.get("flat_rate_hours") or 0) * rate + fixed
    return float(row.get("rate_sensitive_factor") or 0) * rate + fixed


def review_status(row: pd.Series, simulated: float, rate: float) -> str:
    award_base = float(row.get("award_minimum_base_rate") or 0)
    minimum = float(row.get("award_minimum_entitlement") or 0)
    if rate < award_base - 0.005:
        return "POTENTIAL_BASE_RATE_UNDERPAYMENT"
    if simulated < minimum - 0.05:
        return "POTENTIAL_UNDERPAYMENT"
    if float(row.get("review_shift_count") or 0) > 0:
        return "REQUIRES_AWARD_REVIEW"
    return "SIMULATION_MEETS_MINIMUM"


def build_master(all_rows: pd.DataFrame) -> pd.DataFrame:
    if all_rows.empty:
        return all_rows
    output = []
    group_cols = ["employee_id", "employee_name", "calendar_year"]
    for _, group in all_rows.groupby(group_cols, dropna=False, sort=True):
        selected = group[group.get("selected_scenario", False).fillna(False)] if "selected_scenario" in group.columns else pd.DataFrame()
        if not selected.empty:
            row = selected.sort_values("confirmed_at", na_position="last").iloc[-1].to_dict()
            row["scenario_confirmation_status"] = "SELECTED_SCENARIO_CONFIRMED"
            row["minimum_entitlement_low"] = group["award_minimum_entitlement"].min()
            row["minimum_entitlement_high"] = group["award_minimum_entitlement"].max()
            output.append(row)
            continue
        first = group.iloc[0].to_dict()
        first.update(
            {
                "scenario_id": None,
                "scenario_classification_code": None,
                "scenario_classification_name": None,
                "classification_family": None,
                "scenario_level": None,
                "scenario_pay_point": None,
                "scenario_employment_type": None,
                "scenario_work_group": None,
                "scenario_confirmation_status": "SCENARIO_NOT_SELECTED",
                "review_status": "MISSING_PAY_RATE_CONFIRMATION" if pd.isna(first.get("confirmation_id")) else "RATE_CONFIRMED_SCENARIO_NOT_SELECTED",
                "minimum_entitlement_low": group["award_minimum_entitlement"].min(),
                "minimum_entitlement_high": group["award_minimum_entitlement"].max(),
                "award_minimum_base_rate": group["award_minimum_base_rate"].min(),
                "award_minimum_entitlement": None,
                "confirmed_rate_simulated_pay": None,
                "confirmed_rate_variance": None,
            }
        )
        output.append(first)
    return pd.DataFrame(output)


st.title("AuditHero — Roster Pay Simulator & Review")
st.caption(
    "Use roster evidence immediately, explore hypothetical hourly rates, then save confirmed rate evidence later. "
    "Simulated pay is not treated as actual payroll evidence."
)

try:
    employees = query_df(
        f"""
        SELECT DISTINCT CAST(employee_id AS STRING) AS employee_id, employee_name
        FROM `{CATALOG}`.`gold`.`v_pay_simulation_employee_year`
        ORDER BY employee_name, employee_id
        """
    )
except Exception as exc:
    st.error("The roster simulation layer is not ready. Run 'AuditHero - Setup Pay Simulation & Review' after AuditHero Setup.")
    st.exception(exc)
    st.stop()

if employees.empty:
    st.warning("No roster simulation rows exist yet. Run a reviewed-file audit containing roster/timesheet evidence first.")
    st.stop()

employee_options = {
    f"{row.employee_name or row.employee_id} [{row.employee_id}]": str(row.employee_id)
    for row in employees.itertuples(index=False)
}
selected_employee_label = st.sidebar.selectbox("Employee", list(employee_options.keys()))
employee_id = employee_options[selected_employee_label]

years = query_df(
    f"SELECT DISTINCT calendar_year FROM `{CATALOG}`.`gold`.`v_pay_simulation_employee_year` WHERE employee_id = ? ORDER BY calendar_year DESC",
    [employee_id],
)
calendar_year = int(st.sidebar.selectbox("Year", years["calendar_year"].dropna().astype(int).tolist()))

scenarios = query_df(
    f"""
    SELECT *
    FROM `{CATALOG}`.`gold`.`v_pay_simulation_employee_year`
    WHERE employee_id = ? AND calendar_year = ?
    ORDER BY classification_family, scenario_level, scenario_pay_point, scenario_employment_type, scenario_id
    """,
    [employee_id, calendar_year],
)

if scenarios.empty:
    st.warning("No simulation scenarios were calculated for this employee/year.")
    st.stop()

scenario_labels = {}
for row in scenarios.itertuples(index=False):
    label = (
        f"{row.classification_family} | {row.scenario_classification_name or row.scenario_classification_code} | "
        f"L{row.scenario_level or '-'} P{row.scenario_pay_point or '-'} | {row.scenario_employment_type} | {row.scenario_work_group}"
    )
    scenario_labels[label] = row.scenario_id

existing_confirmation = query_df(
    f"""
    SELECT * FROM `{CATALOG}`.`gold`.`v_pay_rate_confirmations_latest`
    WHERE CAST(employee_id AS STRING) = ? AND calendar_year = ?
    LIMIT 1
    """,
    [employee_id, calendar_year],
)

confirmed_scenario = None if existing_confirmation.empty else existing_confirmation.iloc[0].get("selected_scenario_id")
default_index = 0
if confirmed_scenario:
    for i, value in enumerate(scenario_labels.values()):
        if value == confirmed_scenario:
            default_index = i
            break

selected_scenario_label = st.sidebar.selectbox("SCHADS scenario", list(scenario_labels.keys()), index=default_index)
scenario_id = scenario_labels[selected_scenario_label]
summary = scenarios[scenarios["scenario_id"] == scenario_id].iloc[0]

model_label = st.sidebar.radio(
    "Hypothetical pay model",
    ["Base + SCHADS multipliers", "Flat / loaded hourly rate"],
    help=(
        "Base + SCHADS multipliers assumes the chosen base is used wherever the Award calculation uses a rate multiplier. "
        "Flat / loaded assumes the chosen rate is paid for rostered worked hours and compares that outcome with the Award minimum."
    ),
)
pay_model = "FLAT_LOADED_HOURLY" if model_label.startswith("Flat") else "BASE_PLUS_SCHADS_MULTIPLIERS"

award_floor = float(summary.get("award_minimum_base_rate") or 0)
slider_max = max(100.0, math.ceil(award_floor + 10))
confirmed_rate = None if existing_confirmation.empty else existing_confirmation.iloc[0].get("confirmed_hourly_rate")
default_rate = float(confirmed_rate) if confirmed_rate is not None and not pd.isna(confirmed_rate) else award_floor
default_rate = min(max(default_rate, award_floor), slider_max)

hypothetical_rate = st.sidebar.slider(
    "Explore hourly base rate",
    min_value=round(award_floor, 2),
    max_value=float(slider_max),
    value=round(default_rate, 2),
    step=0.25,
    format="$%.2f",
)

simulated_total = simulate(summary, hypothetical_rate, pay_model)
minimum_total = float(summary.get("award_minimum_entitlement") or 0)
variance = simulated_total - minimum_total
status = review_status(summary, simulated_total, hypothetical_rate)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Award minimum base", money(award_floor))
m2.metric("Roster hours", f"{float(summary.get('roster_worked_hours') or 0):,.2f}")
m3.metric("SCHADS minimum entitlement", money(minimum_total))
m4.metric("Simulated pay", money(simulated_total), delta=money(variance))
m5.metric("Review shifts", int(summary.get("review_shift_count") or 0))

if status.startswith("POTENTIAL"):
    st.error(f"{status}: simulated outcome is {money(abs(min(variance, 0)))} below the calculated minimum." )
elif status == "REQUIRES_AWARD_REVIEW":
    st.warning("The numeric simulation meets the minimum, but one or more Award/evidence findings still require review.")
else:
    st.success("The selected hypothetical model meets the calculated minimum. Actual payroll is still unconfirmed unless evidence has been saved/imported.")

break_even = summary.get("flat_loaded_break_even_rate") if pay_model == "FLAT_LOADED_HOURLY" else summary.get("award_structure_break_even_rate")
st.info(
    f"Break-even hourly rate for this model: {money(break_even)}. "
    f"Fixed Award-linked components in this scenario/year: {money(summary.get('fixed_award_amount'))}."
)

rates = np.arange(round(award_floor, 2), slider_max + 0.001, 0.25)
curve = pd.DataFrame({"Hourly rate": rates})
curve["Base + SCHADS multipliers"] = float(summary.get("rate_sensitive_factor") or 0) * rates + float(summary.get("fixed_award_amount") or 0)
curve["Flat / loaded hourly"] = float(summary.get("flat_rate_hours") or 0) * rates + float(summary.get("fixed_award_amount") or 0)
curve["SCHADS minimum"] = minimum_total
st.subheader("Pay outcome curve")
st.line_chart(curve.set_index("Hourly rate"), height=320)
st.caption("The curve is sampled every $0.25 for display. The simulator equation accepts exact cent values when you save a confirmation.")

terms = query_df(
    f"""
    SELECT *
    FROM `{CATALOG}`.`gold`.`v_pay_simulation_terms_latest`
    WHERE employee_id = ? AND calendar_year = ? AND scenario_id = ?
    ORDER BY shift_start
    """,
    [employee_id, calendar_year, scenario_id],
)
if not terms.empty:
    terms = terms.copy()
    if pay_model == "FLAT_LOADED_HOURLY":
        terms["simulated_pay"] = terms["flat_rate_hours"].fillna(0) * hypothetical_rate + terms["fixed_award_amount"].fillna(0)
    else:
        terms["simulated_pay"] = terms["rate_sensitive_factor"].fillna(0) * hypothetical_rate + terms["fixed_award_amount"].fillna(0)
    terms["simulation_variance"] = terms["simulated_pay"] - terms["award_minimum_entitlement"].fillna(0)
    terms["simulation_status"] = np.where(terms["simulation_variance"] < -0.05, "POTENTIAL_UNDERPAYMENT", np.where(terms["review_required"] > 0, "REQUIRES_REVIEW", "MEETS_MINIMUM"))
    st.subheader("Shift-by-shift simulation")
    st.dataframe(
        terms[[
            "shift_start", "shift_end", "roster_worked_hours", "award_minimum_base_rate",
            "award_minimum_entitlement", "fixed_award_amount", "simulated_pay",
            "simulation_variance", "simulation_status", "review_flags"
        ]],
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.subheader("Confirm rate evidence")
if existing_confirmation.empty:
    st.error("Payroll/base-rate confirmation is missing for this employee/year. Simulation remains hypothetical.")
else:
    c = existing_confirmation.iloc[0]
    st.success(
        f"Latest saved rate: {money(c.get('confirmed_hourly_rate'))} | {c.get('pay_model')} | "
        f"source={c.get('source_type')} | confirmed by {c.get('confirmed_by')} at {c.get('confirmed_at')}"
    )

with st.form("confirm_rate_form"):
    exact_rate = st.number_input(
        "Confirmed base hourly rate",
        min_value=0.0,
        max_value=500.0,
        value=float(confirmed_rate) if confirmed_rate is not None and not pd.isna(confirmed_rate) else float(hypothetical_rate),
        step=0.01,
        format="%.2f",
    )
    confirmation_model_label = st.selectbox(
        "How was this hourly rate used?",
        ["Base + SCHADS multipliers", "Flat / loaded hourly rate"],
        index=1 if (not existing_confirmation.empty and existing_confirmation.iloc[0].get("pay_model") == "FLAT_LOADED_HOURLY") else 0,
    )
    source_type = st.selectbox("Evidence source", ["MANUAL_CONFIRMATION", "PAYROLL_BASE_RATE", "EMPLOYMENT_CONTRACT", "OTHER"])
    source_reference = st.text_input("Source/reference", placeholder="e.g. Payroll export May 2025, contract clause, payslip reference")
    notes = st.text_area("Notes")
    save_confirmation = st.form_submit_button("Save confirmation", type="primary")

if save_confirmation:
    confirmation_id = str(uuid.uuid4())
    previous_id = None if existing_confirmation.empty else existing_confirmation.iloc[0].get("confirmation_id")
    confirmation_model = "FLAT_LOADED_HOURLY" if confirmation_model_label.startswith("Flat") else "BASE_PLUS_SCHADS_MULTIPLIERS"
    execute(
        f"""
        INSERT INTO `{CATALOG}`.`silver`.`pay_rate_confirmations` (
          confirmation_id, employee_id, calendar_year, effective_from, effective_to,
          confirmed_hourly_rate, pay_model, selected_scenario_id, source_type,
          source_reference, notes, confirmed_by, confirmed_at, status, supersedes_confirmation_id
        ) VALUES (?, ?, ?, MAKE_DATE(?, 1, 1), MAKE_DATE(?, 12, 31), ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP(), 'ACTIVE', ?)
        """,
        [
            confirmation_id, employee_id, calendar_year, calendar_year, calendar_year,
            float(exact_rate), confirmation_model, scenario_id, source_type,
            source_reference or None, notes or None, current_user(), previous_id,
        ],
    )
    st.success("Rate confirmation saved. The previous confirmation remains in history for auditability.")
    st.cache_data.clear()
    st.rerun()

st.divider()
st.subheader("Master employee review & export")
all_master = query_df(f"SELECT * FROM `{CATALOG}`.`gold`.`v_pay_simulation_master` ORDER BY employee_name, calendar_year, scenario_id")
master = build_master(all_master)
if not master.empty:
    preferred_columns = [
        "employee_id", "employee_name", "calendar_year", "scenario_confirmation_status",
        "scenario_id", "classification_family", "scenario_classification_code", "scenario_classification_name",
        "scenario_level", "scenario_pay_point", "scenario_employment_type", "scenario_work_group",
        "award_minimum_base_rate", "confirmed_hourly_rate", "confirmed_pay_model",
        "minimum_entitlement_low", "minimum_entitlement_high", "award_minimum_entitlement",
        "confirmed_rate_simulated_pay", "confirmed_rate_variance", "review_status", "recommendation",
        "confirmation_source_type", "confirmation_source_reference", "confirmation_notes", "confirmed_by", "confirmed_at"
    ]
    master = master[[c for c in preferred_columns if c in master.columns]]
    st.dataframe(master, use_container_width=True, hide_index=True)

    csv_bytes = master.to_csv(index=False).encode("utf-8")
    st.download_button("Export master CSV", csv_bytes, file_name="audithero_pay_review_master.csv", mime="text/csv")

    history = query_df(f"SELECT * FROM `{CATALOG}`.`silver`.`pay_rate_confirmations` ORDER BY confirmed_at DESC")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        master.to_excel(writer, sheet_name="Master review", index=False)
        all_master.to_excel(writer, sheet_name="All scenario outcomes", index=False)
        history.to_excel(writer, sheet_name="Confirmation history", index=False)
    st.download_button(
        "Export master Excel workbook",
        output.getvalue(),
        file_name="audithero_pay_review_master.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with st.expander("Important interpretation"):
    st.markdown(
        """
- **SCHADS minimum entitlement** is produced by AuditHero's deterministic Award engine from the roster/timesheet evidence and selected scenario.
- **Simulated pay** is a what-if calculation. It is not actual payroll evidence.
- A saved hourly-rate confirmation records that rate and its evidence source, but it still does not prove the employee's total gross payment unless payroll earnings are supplied.
- When payroll files are added later through the normal Preview → Reviewed Uploaded Files workflow, use the definitive Actual vs Expected audit for final reconciliation.
- If classification, employment type, breaks, sleepover grouping or other evidence is uncertain, the scenario remains a review tool rather than a definitive classification decision.
        """
    )
