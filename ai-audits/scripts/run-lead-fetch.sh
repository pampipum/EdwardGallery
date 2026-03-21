#!/bin/bash
# run-lead-fetch.sh - Weekly Swiss lead fetch for AI Audits project

set -e

PROJECT_DIR="/root/.openclaw/workspace/ai-audits"
cd "$PROJECT_DIR" || exit 1

# Ensure data directory exists
mkdir -p data

# Log start time
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting lead fetch..." >> data/cron-lead-fetch.log

# Run the lead fetch script
node scripts/fetch-swiss-leads.mjs >> data/cron-lead-fetch.log 2>&1

# Log completion
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Lead fetch completed." >> data/cron-lead-fetch.log
