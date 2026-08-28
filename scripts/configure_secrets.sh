#!/usr/bin/env bash
set -euo pipefail
SCOPE="${1:-audithero}"
databricks secrets create-scope "$SCOPE" 2>/dev/null || true
put(){ read -rsp "Enter $1: " V; echo; databricks secrets put-secret "$SCOPE" "$1" --string-value "$V"; }
put EH_ORGANISATION_ID; put EH_HR_CLIENT_ID; put EH_HR_CLIENT_SECRET; put EH_HR_REFRESH_TOKEN
read -rp "Configure Employment Hero Payroll API? [y/N] " Y
if [[ "${Y,,}" == y ]]; then put EH_PAYROLL_API_KEY; put EH_PAYROLL_BUSINESS_ID; fi
