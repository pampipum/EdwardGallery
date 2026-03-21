#!/bin/bash
# setup-cron-jobs.sh - Install cron jobs for workspace projects

set -e

echo "Setting up cron jobs for workspace projects..."
echo ""

# Get current crontab
CURRENT_CRONTAB=$(crontab -l 2>/dev/null || echo "")

# Define new jobs (avoiding duplicates)
NEW_JOBS=""

# AI Audits - Weekly lead fetch (Mondays at 8:00 AM, Europe/Zurich)
AI_AUDITS_LEAD="0 8 * * 1 cd /root/.openclaw/workspace/ai-audits && bash scripts/run-lead-fetch.sh"

# AI Audits - Weekly critique email (Wednesdays at 10:00 AM, Europe/Zurich)
AI_AUDITS_CRITIQUE="0 10 * * 3 cd /root/.openclaw/workspace/ai-audits && bash scripts/run-critique-email.sh"

# Check if jobs already exist
if ! echo "$CURRENT_CRONTAB" | grep -q "run-lead-fetch.sh"; then
  NEW_JOBS="${NEW_JOBS}${AI_AUDITS_LEAD}"$'\n'
  echo "✓ Adding AI Audits weekly lead fetch (Mondays 8:00 AM)"
else
  echo "⊘ AI Audits lead fetch already scheduled"
fi

if ! echo "$CURRENT_CRONTAB" | grep -q "run-critique-email.sh"; then
  NEW_JOBS="${NEW_JOBS}${AI_AUDITS_CRITIQUE}"$'\n'
  echo "✓ Adding AI Audits weekly critique email (Wednesdays 10:00 AM)"
else
  echo "⊘ AI Audits critique email already scheduled"
fi

# Add new jobs if any
if [ -n "$NEW_JOBS" ]; then
  # Combine existing and new jobs
  if [ -n "$CURRENT_CRONTAB" ]; then
    (echo "$CURRENT_CRONTAB"; echo "$NEW_JOBS") | crontab -
  else
    echo "$NEW_JOBS" | crontab -
  fi
  echo ""
  echo "✓ Cron jobs installed successfully"
else
  echo ""
  echo "⊘ No new jobs to add"
fi

echo ""
echo "Current crontab:"
echo "================"
crontab -l
