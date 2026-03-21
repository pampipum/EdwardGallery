#!/bin/bash
# backup-assets.sh - Backup Script
# Identifies non-code assets (PDFs, images, databases, memory files), compresses, and uploads.
# Upload target preference:
#  1) Box (BOX_ACCESS_TOKEN)
#  2) rsync fallback (REMOTE_BACKUP_USER/HOST/PATH)
# Keeps last 14 daily backups locally.
# Runs daily at 3:00 AM.
#
# Usage:
#   backup-assets.sh [--dry-run]

set -e

WORKSPACE="/root/.openclaw/workspace"
LOGS_DIR="$WORKSPACE/logs"
BACKUP_DIR="$WORKSPACE/backups"
TIMESTAMP_DAY=$(date +%Y-%m-%d)
BACKUP_FILE="$BACKUP_DIR/backup-$TIMESTAMP_DAY.tar.gz"
LOG_FILE="$LOGS_DIR/backup-$TIMESTAMP_DAY.log"

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
fi

mkdir -p "$BACKUP_DIR" "$LOGS_DIR"

# Log everything to file + stdout
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "💾 Backup Script - $(date)"
log "Workspace: $WORKSPACE"
log "Dry run: $DRY_RUN"

BOX_ACCESS_TOKEN="${BOX_ACCESS_TOKEN:-}"
REMOTE_BACKUP_USER="${REMOTE_BACKUP_USER:-}"
REMOTE_BACKUP_HOST="${REMOTE_BACKUP_HOST:-}"
REMOTE_BACKUP_PATH="${REMOTE_BACKUP_PATH:-/backups/openclaw}"
RETENTION_DAYS=14

ASSET_LIST="$BACKUP_DIR/.asset-list-$TIMESTAMP_DAY.txt"
> "$ASSET_LIST"

log "📋 Identifying assets…"

# Memory files
if [ -d "$WORKSPACE/memory" ]; then
  find "$WORKSPACE/memory" -type f \( -name "*.md" -o -name "*.json" \) >> "$ASSET_LIST" 2>/dev/null || true
fi

# Docs
if [ -d "$WORKSPACE/docs" ]; then
  find "$WORKSPACE/docs" -type f -name "*.md" >> "$ASSET_LIST" 2>/dev/null || true
fi

# Logs (keep last 30 days only)
if [ -d "$WORKSPACE/logs" ]; then
  find "$WORKSPACE/logs" -type f \( -name "*.log" -o -name "*.md" \) -mtime -30 >> "$ASSET_LIST" 2>/dev/null || true
fi

# PDFs, images
find "$WORKSPACE" -type f \( -name "*.pdf" -o -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.gif" -o -name "*.webp" \) \
  ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/backups/*" >> "$ASSET_LIST" 2>/dev/null || true

# Light DB-ish files
find "$WORKSPACE" -type f \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \) \
  ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/backups/*" >> "$ASSET_LIST" 2>/dev/null || true

# Dedupe
sort -u "$ASSET_LIST" -o "$ASSET_LIST" || true

ASSET_COUNT=$(wc -l < "$ASSET_LIST" 2>/dev/null || echo 0)
log "Total assets: $ASSET_COUNT"

if [ "$ASSET_COUNT" -eq 0 ]; then
  log "⚠️  No assets found; exiting."
  rm -f "$ASSET_LIST"
  exit 0
fi

log "Sample (first 20):"
head -20 "$ASSET_LIST" | sed 's/^/  - /'

if [ "$DRY_RUN" = true ]; then
  log "✅ Dry run complete (no archive created, no upload, no retention cleanup)."
  rm -f "$ASSET_LIST"
  exit 0
fi

log "📦 Creating archive: $BACKUP_FILE"
# tar from file list (paths are absolute)
if tar -czf "$BACKUP_FILE" -T "$ASSET_LIST"; then
  BACKUP_SIZE=$(du -h "$BACKUP_FILE" | awk '{print $1}')
  log "✅ Archive created ($BACKUP_SIZE)"
else
  log "❌ Failed to create archive"
  rm -f "$ASSET_LIST"
  exit 1
fi

# Upload to Box
if [ -n "$BOX_ACCESS_TOKEN" ]; then
  log "☁️  Uploading to Box…"
  UPLOAD_RESPONSE=$(curl -s -X POST "https://upload.box.com/api/2.0/files/content" \
    -H "Authorization: Bearer $BOX_ACCESS_TOKEN" \
    -F "attributes={\"name\":\"backup-$TIMESTAMP_DAY.tar.gz\",\"parent\":{\"id\":\"0\"}}" \
    -F "file=@$BACKUP_FILE" || true)

  if echo "$UPLOAD_RESPONSE" | grep -q '"type"\s*:\s*"file"'; then
    FILE_ID=$(echo "$UPLOAD_RESPONSE" | sed -n 's/.*"id"\s*:\s*"\([0-9A-Za-z]\+\)".*/\1/p' | head -1)
    log "✅ Uploaded to Box (file id: ${FILE_ID:-unknown})"
  else
    log "⚠️  Box upload failed; response (truncated):"
    echo "$UPLOAD_RESPONSE" | head -c 4000
  fi
else
  log "⚠️  BOX_ACCESS_TOKEN not set; skipping Box upload."
fi

# rsync fallback
if [ -n "$REMOTE_BACKUP_USER" ] && [ -n "$REMOTE_BACKUP_HOST" ]; then
  log "🔄 Syncing to remote via rsync…"
  if rsync -avz -e ssh "$BACKUP_FILE" "$REMOTE_BACKUP_USER@$REMOTE_BACKUP_HOST:$REMOTE_BACKUP_PATH/"; then
    log "✅ Remote sync complete"
  else
    log "⚠️  Remote sync failed"
  fi
fi

# Retention cleanup
log "🧹 Retention cleanup: keep last $RETENTION_DAYS days"
REMOVED=0
while IFS= read -r old; do
  [ -z "$old" ] && continue
  rm -f "$old" && REMOVED=$((REMOVED+1))
done < <(find "$BACKUP_DIR" -name "backup-*.tar.gz" -type f -mtime +$RETENTION_DAYS 2>/dev/null || true)
log "Removed old backups: $REMOVED"

rm -f "$ASSET_LIST"

log "✅ Backup complete"
log "Archive: $BACKUP_FILE"
log "Log: $LOG_FILE"

exit 0
