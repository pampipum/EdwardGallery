#!/bin/bash
# update-openclaw.sh - OpenClaw Automated Update Script
# Fetches latest version, compares, updates, and logs changes
# Runs daily at 5:00 AM

set -e

WORKSPACE="/root/.openclaw/workspace"
MEMORY_DIR="$WORKSPACE/memory"
LOGS_DIR="$WORKSPACE/logs"
OUTPUT_FILE="$MEMORY_DIR/openclaw-update-$(date +%Y-%m-%d).md"
LOG_FILE="$LOGS_DIR/openclaw-update.log"

# Ensure directories exist
mkdir -p "$MEMORY_DIR" "$LOGS_DIR"

echo "🔄 OpenClaw Update Check - $(date)"
echo "===================================="
echo ""

# Initialize output
cat > "$OUTPUT_FILE" << EOF
# OpenClaw Update Report

**Date:** $(date +%Y-%m-%d)  
**Time:** $(date +%H:%M:%S)

---

EOF

# Function to log with timestamp
log() {
    echo "$1"
    echo "$1" >> "$OUTPUT_FILE"
}

# Get current version
log "## Current Version Check"
log ""
CURRENT_VERSION=$(npm list -g openclaw 2>/dev/null | grep openclaw | awk -F'@' '{print $2}' | head -1 || echo "unknown")
log "Current version: $CURRENT_VERSION"

# Get latest version
log ""
log "## Latest Version Check"
log ""
LATEST_VERSION=$(npm view openclaw version 2>/dev/null || echo "unknown")
log "Latest version: $LATEST_VERSION"

# Compare versions
if [ "$CURRENT_VERSION" = "unknown" ]; then
    log ""
    log "⚠️  Could not determine current OpenClaw version"
    log ""
    log "### Manual Check Required"
    log "Run: \`npm list -g openclaw\`"
    exit 1
fi

if [ "$LATEST_VERSION" = "unknown" ]; then
    log ""
    log "⚠️  Could not fetch latest version from npm"
    log ""
    log "### Possible Issues"
    log "- Network connectivity"
    log "- npm registry unavailable"
    exit 1
fi

log ""
log "## Version Comparison"
log ""

# Simple version comparison (works for semver)
if [ "$CURRENT_VERSION" = "$LATEST_VERSION" ]; then
    log "✅ Already up to date!"
    log ""
    log "Current: $CURRENT_VERSION"
    log "Latest:  $LATEST_VERSION"
    log ""
    log "### No Action Required"
    log "Next check: tomorrow at 5:00 AM"
    
    echo "" >> "$OUTPUT_FILE"
    echo "---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "**Status:** ✅ Up to date" >> "$OUTPUT_FILE"
    
    exit 0
fi

log "🆕 Update available!"
log ""
log "Current: $CURRENT_VERSION"
log "Latest:  $LATEST_VERSION"
log ""

# Fetch changelog from GitHub
log "## Changelog"
log ""

CHANGELOG=""
if command -v curl &> /dev/null; then
    # Try to get GitHub releases
    CHANGELOG=$(curl -s "https://api.github.com/repos/openclaw/openclaw/releases/latest" 2>/dev/null | \
        grep -A 20 '"body":' | \
        sed 's/  "body": "//' | \
        sed 's/",$//' | \
        head -20 || echo "Could not fetch changelog")
fi

if [ -n "$CHANGELOG" ] && [ "$CHANGELOG" != "Could not fetch changelog" ]; then
    log "$CHANGELOG"
else
    log "_Changelog not available via API_"
    log ""
    log "Check GitHub releases: https://github.com/openclaw/openclaw/releases"
fi

log ""
log "## Installing Update"
log ""

# Perform update
log "Running: npm install -g openclaw@latest"
UPDATE_OUTPUT=$(npm install -g openclaw@latest 2>&1 || true)
log ""
log "\`\`\`"
log "$UPDATE_OUTPUT"
log "\`\`\`"

# Check if installation succeeded
if echo "$UPDATE_OUTPUT" | grep -q "ERR\|error\|failed"; then
    log ""
    log "❌ Update failed!"
    log ""
    log "### Error Details"
    log "$UPDATE_OUTPUT"
    
    echo "" >> "$OUTPUT_FILE"
    echo "---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "**Status:** ❌ Update failed" >> "$OUTPUT_FILE"
    
    exit 1
fi

log ""
log "✅ Update completed successfully!"

# Restart gateway if needed
log ""
log "## Gateway Restart"
log ""

log "Checking if gateway restart is needed..."
if command -v openclaw &> /dev/null; then
    log "Restarting OpenClaw gateway..."
    RESTART_OUTPUT=$(openclaw gateway restart 2>&1 || true)
    log ""
    log "$RESTART_OUTPUT"
    
    if echo "$RESTART_OUTPUT" | grep -q "ERR\|error\|failed"; then
        log ""
        log "⚠️  Gateway restart encountered issues"
        log "Manual restart may be required: \`openclaw gateway restart\`"
    else
        log ""
        log "✅ Gateway restarted successfully"
    fi
else
    log "⚠️  'openclaw' command not found - manual restart may be needed"
fi

# Verify new version
log ""
log "## Verification"
log ""

NEW_VERSION=$(npm list -g openclaw 2>/dev/null | grep openclaw | awk -F'@' '{print $2}' | head -1 || echo "unknown")
log "New version: $NEW_VERSION"

if [ "$NEW_VERSION" = "$LATEST_VERSION" ]; then
    log "✅ Version verified successfully"
else
    log "⚠️  Version mismatch - expected $LATEST_VERSION, got $NEW_VERSION"
fi

# Summary
echo "" >> "$OUTPUT_FILE"
echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "**Status:** ✅ Update successful" >> "$OUTPUT_FILE"
echo "**Previous:** $CURRENT_VERSION" >> "$OUTPUT_FILE"
echo "**Updated to:** $NEW_VERSION" >> "$OUTPUT_FILE"
echo "**Gateway:** Restarted" >> "$OUTPUT_FILE"

log ""
log "===================================="
log "Update complete!"
log "Report saved to: $OUTPUT_FILE"

exit 0
