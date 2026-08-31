# SCHADS rules and evidence

AuditHero applies a source-controlled, effective-dated SCHADS rule library. The system is designed to calculate only where the available facts support a reliable rule selection and to flag uncertainty for review.

## Effective-dated rule selection

Rates, conditions and allowances are versioned by operative date. Pay-period information matters because Award changes can apply from the first full pay period commencing on or after an operative date.

AuditHero therefore prefers explicit pay-period dates or a supplied pay-runs dataset rather than selecting a rate from the shift date alone.

## Classification families

The included rule library supports the classification families configured in `rules/MA000100/`, including supported SACS and Home Care disability-care classifications for the covered historical versions.

A source payroll classification must be mapped to a canonical AuditHero classification code before an automated entitlement can be trusted.

## Industrial instrument coverage

Historical classification is not, by itself, legal proof that SCHADS applied. The industrial-instrument history register records the effective coverage evidence. Where an enterprise agreement, IFA or other arrangement applies, AuditHero should not silently present a SCHADS-only result as final remediation.

## Ordinary penalties and shiftwork

The rule library applies the supported weekday/weekend/public-holiday and shiftwork structures using the employee's employment type, classification, location and shift facts.

## Overtime

AuditHero uses roster evidence and daily/weekly/fortnightly thresholds where supported. If the system cannot determine which exact hours should be repriced without stacking or ambiguity, it flags the period for review instead of allocating overtime arbitrarily.

## Broken shifts

AuditHero groups eligible separate work periods and applies supported broken-shift conditions/allowances where the gaps and evidence can be established. Agreement requirements and span/overtime interactions that cannot be proven are surfaced for review.

## Sleepovers

A sleepover span is treated as a sleepover allowance period, not automatically as eight ordinary worked hours. Active work during a sleepover must be represented as active-work evidence. Effective-dated rules account for the changed surrounding-work arrangements where supported.

## Part-time patterns

Where a SCHADS rule depends on the employee's written agreed regular pattern/guaranteed hours, AuditHero uses the effective-dated part-time pattern and variation evidence. It does not assume that a roster alone is the written agreement.

## Public holidays

State public holidays can be supplemented by controlled local/substituted holiday overrides. A location key lets a local holiday apply only to the relevant work location.

## Rest and meal evidence

Rest-after-overtime and worked-through/delayed meal scenarios can depend on facts not normally present in basic payroll exports. Supply the controlled event evidence where applicable.

## Supplemental events and TOIL

Event-based calculations such as on-call, recall, remote work, higher duties and TOIL use dedicated event/register inputs. Unsupported or incomplete event facts remain review findings rather than being automatically added to remediation totals.

## Updating the rule library

Administrators should update the effective-dated JSON packs only from authoritative Award/pay-guide sources, retain source metadata, add regression cases and rerun platform self-tests before using a new version in production.

See [Administration](ADMINISTRATION.md).
