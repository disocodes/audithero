# Rule library guide

SCHADS rules are kept as effective-dated JSON so a July change does not require a new calculation notebook.

## Three independent pack types

**Rates** contain canonical classification codes and base hourly rates. **Conditions** contain minimum engagement, weekend/public-holiday multipliers, shiftwork, overtime structure, broken shift and sleepover conditions. **Allowances** contain effective-dated dollar amounts.

This separation matters because rule changes and rate changes can start on different dates. The 1 June 2026 sleepover variation therefore has its own condition pack, while the next wage-rate pack begins in July.

## Adding an annual change

1. Obtain the official Fair Work source.
2. Add a new JSON pack under the relevant folder.
3. Record the source and verification status.
4. Add it to `manifest.json` in chronological order.
5. Add regression cases under `tests/`.
6. Run `pytest -q`.
7. Redeploy and run the Setup job to refresh `ref.*` Delta tables.
8. Independently verify the new pack before remediation.

## Effective-date selection

The library selects the latest pack whose `operative_date <= pay_period_start`. This models the common Award requirement that wage changes apply from the first full pay period starting on or after the operative date.

If pay-period start cannot be established, AuditHero flags the calculation rather than silently treating the shift date as conclusive.

## Extending beyond SACS

The supplied historical wage packs cover SACS classifications. Add verified Home Care / Aged Care / other MA000100 classification families using their own canonical classification codes. The engine and version-selection mechanism do not need to change.
