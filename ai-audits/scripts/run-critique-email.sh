#!/bin/bash
# run-critique-email.sh - Weekly presentation critique email for AI Audits project

set -e

PROJECT_DIR="/root/.openclaw/workspace/ai-audits"
cd "$PROJECT_DIR" || exit 1

# Check if AGENTMAIL_API_KEY is set
if [ -z "$AGENTMAIL_API_KEY" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: AGENTMAIL_API_KEY not set" >> data/cron-critique-email.log
  exit 1
fi

# Check if recipient is provided
RECIPIENT="${1:-}"
if [ -z "$RECIPIENT" ]; then
  # Default recipient from environment or skip
  if [ -z "$CRITIQUE_EMAIL_RECIPIENT" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: No recipient specified, skipping" >> data/cron-critique-email.log
    exit 0
  fi
  RECIPIENT="$CRITIQUE_EMAIL_RECIPIENT"
fi

# Ensure data directory exists
mkdir -p data

# Log start time
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting critique email to $RECIPIENT..." >> data/cron-critique-email.log

# Run the email script
node scripts/send-presentation-critique-email.mjs "$RECIPIENT" >> data/cron-critique-email.log 2>&1

# Log completion
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Critique email completed." >> data/cron-critique-email.log
