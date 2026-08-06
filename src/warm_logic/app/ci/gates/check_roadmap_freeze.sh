#!/usr/bin/env bash
set -euo pipefail

LEDGER_DIR="$(cd "$(dirname "$0")/.." && pwd)/ledger"
ROADMAP_FILE="${LEDGER_DIR}/ROADMAP-FREEZE.json"

support_hours_current=22
support_threshold=30
core_red_months=0
core_threshold=2

status_support="OK"
if (( support_hours_current > support_threshold )); then
  status_support="FREEZE"
fi

status_core="OK"
if (( core_red_months >= core_threshold )); then
  status_core="FREEZE"
fi

cat <<EOF > "${ROADMAP_FILE}"
{
  "freeze_conditions": [
    {
      "name": "support_time_limit",
      "threshold_hours_per_month": ${support_threshold},
      "current_month_hours": ${support_hours_current},
      "status": "${status_support}",
      "notes": "Sum of Edition/R-EXT/R-CULT/V-DRIFT support hours."
    },
    {
      "name": "core_red_streak",
      "threshold_months": ${core_threshold},
      "current_red_months": ${core_red_months},
      "status": "${status_core}",
      "notes": "Core repro pipeline red streak review."
    }
  ],
  "last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "ROADMAP-FREEZE ledger updated."
