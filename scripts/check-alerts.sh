#!/bin/bash
# Alert Check Script for OpenClaw
# Scans cron jobs for errors and outputs alert summary

CRON_FILE="/root/.openclaw/cron/jobs.json"
ALERT_STATE="/root/.openclaw/workspace/memory/alert-state.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Optional structured logging (best-effort)
LOG_SYSTEM="/root/.openclaw/workspace/scripts/log-system.sh"
log_event() {
    if [ -x "$LOG_SYSTEM" ]; then
        "$LOG_SYSTEM" log "$1" "$2" "check-alerts" "$3" "${4:-{}}" || true
    fi
}

log_event CRON_JOB INFO "Alert check started" "{\"timestamp\": \"$TIMESTAMP\"}"

echo "🔍 Alert Check - $TIMESTAMP"
echo "================================"

# Check if cron file exists
if [ ! -f "$CRON_FILE" ]; then
    echo "❌ ERROR: Cron jobs file not found: $CRON_FILE"
    log_event SYSTEM_ERROR ERROR "Cron jobs file not found" "{\"cron_file\": \"$CRON_FILE\"}"
    exit 1
fi

# Parse and count errors using Python (more reliable JSON parsing)
ALERT_OUTPUT=$(python3 << 'EOF'
import json
import sys
from datetime import datetime

with open('/root/.openclaw/cron/jobs.json', 'r') as f:
    data = json.load(f)

alerts = []
for job in data.get('jobs', []):
    state = job.get('state', {})
    errors = state.get('consecutiveErrors', 0)
    last_status = state.get('lastStatus', 'ok')

    if errors > 0 or last_status == 'error':
        severity = "HIGH" if errors >= 2 else "MEDIUM"
        last_run = state.get('lastRunAtMs', 0)
        last_run_date = datetime.fromtimestamp(last_run/1000).strftime('%Y-%m-%d') if last_run else 'Unknown'

        alerts.append({
            'severity': severity,
            'name': job.get('name', 'Unknown'),
            'errors': errors,
            'error': state.get('lastError', 'Unknown error'),
            'last_run': last_run_date
        })

if not alerts:
    print("✅ No active alerts - all systems healthy")
    sys.exit(0)

# Sort by severity
alerts.sort(key=lambda x: (0 if x['severity'] == 'HIGH' else 1, -x['errors']))

print(f"🚨 {len(alerts)} alert(s) detected\n")

for i, alert in enumerate(alerts, 1):
    emoji = "🔴" if alert['severity'] == 'HIGH' else "🟡"
    print(f"{emoji} Alert #{i}: {alert['name']}")
    print(f"   Severity: {alert['severity']}")
    print(f"   Errors: {alert['errors']} consecutive")
    print(f"   Issue: {alert['error'][:80]}..." if len(alert['error']) > 80 else f"   Issue: {alert['error']}")
    print(f"   Last Run: {alert['last_run']}")
    print()

print(f"Total: {sum(1 for a in alerts if a['severity'] == 'HIGH')} HIGH | {sum(1 for a in alerts if a['severity'] == 'MEDIUM')} MEDIUM")
EOF
)
ALERT_STATUS=$?

echo "$ALERT_OUTPUT"

# Structured log of result
if echo "$ALERT_OUTPUT" | grep -q "No active alerts"; then
    log_event CRON_JOB INFO "Alert check OK" "{\"status\": \"ok\"}"
else
    log_event ALERT WARNING "Alert check detected issues" "{\"status\": \"alert\"}"
fi

echo ""
echo "================================"
echo "Alert state: $ALERT_STATE"
