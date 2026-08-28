# AuditHero complete platform matrix

AuditHero intentionally has **one shared SCHADS rules/calculation engine** and **two complete deployment stacks**.

| Capability | Databricks | Microsoft Fabric |
|---|---|---|
| Employment Hero HR ingestion | Yes | Yes |
| Employment Hero Payroll ingestion | Yes | Yes |
| Historical date-range audit | Yes | Yes |
| Monthly payroll audit | Yes | Yes |
| Roster ingestion | Yes | Yes |
| Effective-dated SCHADS JSON rules | Yes | Yes |
| SACS and Home Care historical rates | Yes | Yes |
| Broken shifts | Yes | Yes |
| Sleepovers | Yes | Yes |
| Daily / weekly / fortnightly overtime | Yes | Yes |
| Local public holidays | Yes | Yes |
| On-call / recall / remote work | Yes | Yes |
| Higher duties / 24-hour care | Yes | Yes |
| Part-time written-pattern controls | Yes | Yes |
| Rest after overtime | Yes | Yes |
| Meal-break controls | Yes | Yes |
| TOIL register auditing | Yes | Yes |
| EA / IFA / industrial-instrument history | Yes | Yes |
| Readiness scan | Yes | Yes |
| Runtime self-test | Yes | Yes |
| Lakehouse / Delta tables | Unity Catalog Delta | Fabric Lakehouse Delta |
| Scheduled orchestration | Lakeflow Jobs | Fabric Data Factory pipeline + scheduler |
| BI | Databricks AI/BI | Direct Lake semantic model + Power BI report |
| Secrets | Databricks Secrets | Azure Key Vault + NotebookUtils |
| Source-controlled deployment | Databricks Asset Bundle | Fabric REST deployment package |

The shared engine is deliberate. Platform adapters are separate, but payroll logic must not fork.