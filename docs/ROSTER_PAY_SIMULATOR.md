# Roster Pay Simulator

AuditHero can analyse roster evidence before complete payroll evidence is available.

The simulator is designed for situations where the roster, employee identity and SCHADS scenario can be established, but the historical hourly rate or complete payroll result is not yet confirmed.

## What the simulator does

AuditHero first calculates the SCHADS Award outcome from the roster and the selected SCHADS scenario. It then factorises the already-calculated entitlement into rate-sensitive and fixed components.

This lets the dashboard evaluate any selected hourly rate without rerunning the complete 135-scenario Award engine.

The dashboard therefore behaves as continuous what-if analysis rather than storing thousands of duplicate payroll rows for every possible cent value.

## Connected controls

Use **Employee Deep Dive → Live Roster Pay Simulator**.

The simulator exposes:

- Employee through the normal global Employee filter;
- Simulation Year;
- SCHADS scenario;
- Assumed Hourly Rate at cent precision; and
- Pay Interpretation.

The assumed-rate selector is the authoritative rate state for the simulator. Search/type the required value and select it. The same parameter is supplied to the employee summary, shift simulation, Award-component simulation and rate-position visual.

Changing the rate therefore changes the complete simulation section together rather than requiring separate refreshes or independent inputs.

Databricks AI/BI does not safely synchronize two separate widgets that both try to write different values into the same scalar parameter. AuditHero consequently does not create an independent slider control that can conflict with the typed/exact rate. The rate-position visual moves from the same selected-rate parameter and shows the selected value alongside the relevant SCHADS and break-even rates.

## Pay interpretations

### Base + SCHADS multipliers

`BASE_PLUS_SCHADS_MULTIPLIERS`

Use this when the selected hourly amount should be treated as the employee's base hourly rate and the already-established SCHADS penalty/overtime structure should be applied to that base.

### Flat / loaded hourly rate

`FLAT_LOADED_HOURLY`

Use this when the selected hourly amount represents a flat or loaded rate paid across rostered worked hours. Fixed Award-linked components remain separate.

A flat-rate simulation is a coverage analysis. It does not establish that a loaded rate legally absorbed every separate Award entitlement.

## What changes live

The Employee Deep Dive simulation section shows, for the selected employee/year/scenario:

- selected hourly rate;
- SCHADS minimum base rate;
- calculated SCHADS roster entitlement;
- simulated pay;
- variance from SCHADS entitlement;
- Award/evidence review count;
- selected rate versus SCHADS base and break-even rates;
- shift-level simulated pay and variance;
- overtime, penalties, allowances, meal/rest findings and other Award criteria; and
- recommendations/status produced from the selected assumptions.

A rate below the effective SCHADS base or below the calculated roster entitlement is surfaced as potential underpayment. Award/evidence findings remain visible even when the numeric pay simulation exceeds the minimum.

## Break-even rates

AuditHero calculates two useful break-even rates:

- **Award-structure break-even rate** — the base rate which, when passed through the selected SCHADS penalty/overtime structure, equals the calculated minimum entitlement; and
- **Flat/loaded break-even rate** — the flat hourly amount across rostered worked hours, plus fixed Award components, that equals the calculated minimum entitlement.

These are analytical tools and do not prove what the employee was actually paid.

## Hypothetical versus confirmed evidence

Dashboard what-if selections are temporary analytical assumptions.

They are not written into payroll evidence automatically.

When a historical rate has been independently established, run:

**AuditHero - Confirm Employee Pay Rate**

Provide:

- employee ID;
- calendar year;
- confirmed hourly rate;
- pay interpretation;
- selected SCHADS scenario where known;
- evidence source;
- evidence reference; and
- optional notes.

AuditHero stores the confirmation in `silver.pay_rate_confirmations` with confirmation history. A later confirmation supersedes the previous record without deleting the historical record.

A manually confirmed rate is still not proof of complete payroll payment. When detailed payroll/pay-run evidence becomes available, upload/import it and use AuditHero's definitive actual-versus-expected reconciliation.

## Recommended review sequence

1. Load roster evidence and run the reviewed-file audit.
2. Select the employee, year and plausible SCHADS scenario.
3. Use the exact-rate selector to explore possible historical rates.
4. Review break-even rate, overtime, penalties, rest/meal findings and simulated variance.
5. Investigate payroll/payslip/contract evidence.
6. If the hourly rate is established before full payroll is available, use **AuditHero - Confirm Employee Pay Rate**.
7. When complete payroll evidence becomes available, upload/import it and rely on actual-versus-expected reconciliation for the definitive payment result.
