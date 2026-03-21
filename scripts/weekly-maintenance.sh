#!/bin/bash
# weekly-maintenance.sh - Weekly system maintenance tasks

set -e

LOG_DIR="/root/.openclaw/logs"
WORKSPACE="/root/.openclaw/workspace"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting weekly maintenance..."

# Create log directory if needed
mkdir -p "$LOG_DIR"

# 1. Rotate old logs (keep last 7 days)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rotating logs..."
find "$WORKSPACE" -name "*.log" -type f -mtime +7 -exec gzip {} \; 2>/dev/null || true
find "$LOG_DIR" -name "*.log" -type f -mtime +7 -exec gzip {} \; 2>/dev/null || true

# 2. Clean up temp files
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning temp files..."
find "$WORKSPACE" -name "*.tmp" -type f -delete 2>/dev/null || true
find "$WORKSPACE" -name "*.bak" -type f -delete 2>/dev/null || true
find "$WORKSPACE/tmp*" -type d -empty -delete 2>/dev/null || true

# 3. Check disk space
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking disk space..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USAGE" -gt 80 ]; then
  echo "WARNING: Disk usage at ${DISK_USAGE}%" >> "$LOG_DIR/maintenance.log"
fi

# 4. Verify cron jobs are running
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Verifying cron jobs..."
CRON_JOBS=$(crontab -l 2>/dev/null | grep -v "^#" | wc -l)
echo "Active cron jobs: $CRON_JOBS" >> "$LOG_DIR/maintenance.log"

# 5. Check for git changes that need attention
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking git status..."
cd "$WORKSPACE"
if git status --porcelain 2>/dev/null | grep -q "^??"; then
  echo "NOTE: Untracked files in workspace" >> "$LOG_DIR/maintenance.log"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Weekly maintenance completed."
