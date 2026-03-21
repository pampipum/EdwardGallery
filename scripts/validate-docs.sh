#!/bin/bash
# validate-docs.sh - Documentation Validator
# Scans markdown files for broken links, outdated references, and capability mismatches
# Runs daily at 6:00 AM

set -e

WORKSPACE="/root/.openclaw/workspace"
DOCS_DIR="$WORKSPACE/docs"
SKILLS_DIR="$WORKSPACE/skills"
MEMORY_DIR="$WORKSPACE/memory"
LOGS_DIR="$WORKSPACE/logs"
OUTPUT_FILE="$MEMORY_DIR/docs-validation-$(date +%Y-%m-%d).md"

# Ensure directories exist
mkdir -p "$MEMORY_DIR" "$LOGS_DIR"

echo "🔍 Documentation Validation - $(date)"
echo "======================================"
echo ""

# Initialize output
cat > "$OUTPUT_FILE" << EOF
# Documentation Validation Report

**Date:** $(date +%Y-%m-%d)  
**Time:** $(date +%H:%M:%S)  
**Workspace:** $WORKSPACE

---

## Summary

EOF

ISSUES_FOUND=0
WARNINGS=0

# Function to log issues
log_issue() {
    local severity="$1"
    local message="$2"
    local file="${3:-}"
    
    if [ "$severity" = "ERROR" ]; then
        ((ISSUES_FOUND++))
        echo "❌ $message"
        if [ -n "$file" ]; then
            echo "   File: $file"
        fi
        echo "" >> "$OUTPUT_FILE"
        echo "### ❌ $message" >> "$OUTPUT_FILE"
        [ -n "$file" ] && echo "**File:** $file" >> "$OUTPUT_FILE"
    else
        ((WARNINGS++)) || true
        echo "⚠️  $message"
        if [ -n "$file" ]; then
            echo "   File: $file"
        fi
        echo "" >> "$OUTPUT_FILE"
        echo "### ⚠️  $message" >> "$OUTPUT_FILE"
        [ -n "$file" ] && echo "**File:** $file" >> "$OUTPUT_FILE"
    fi
}

# 1. Check for broken markdown links (basic check)
echo "📋 Checking markdown links..."
echo "" >> "$OUTPUT_FILE"
echo "## Markdown Link Check" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for md_file in $(find "$WORKSPACE" -name "*.md" -type f 2>/dev/null | grep -v node_modules | grep -v .git); do
    # Extract relative links and check if they exist
    while IFS= read -r link; do
        [ -z "$link" ] && continue

        # Skip external links and anchors
        if [[ "$link" =~ ^http ]] || [[ "$link" =~ ^# ]]; then
            continue
        fi

        # Get directory of current file
        file_dir=$(dirname "$md_file")

        # Remove anchor from link
        clean_link=$(echo "$link" | sed 's/#.*//')

        # Check if file exists (resolve relative to current file, then workspace)
        if [ -n "$clean_link" ] && [ ! -f "$file_dir/$clean_link" ] && [ ! -f "$WORKSPACE/$clean_link" ]; then
            # Skip common patterns that are OK
            if [[ ! "$clean_link" =~ ^mailto: ]] && [[ ! "$clean_link" =~ ^/ ]]; then
                log_issue "WARN" "Potentially broken link: $clean_link" "$md_file"
            fi
        fi
    done < <(python3 - "$md_file" <<'PY'
import re, sys
p = sys.argv[1]
text = open(p, 'r', encoding='utf-8', errors='ignore').read()
# Basic markdown link extraction: [text](target)
for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
    print(m.group(1).strip())
PY
    )
done

if [ $WARNINGS -eq 0 ] && [ $ISSUES_FOUND -eq 0 ]; then
    echo "✅ No broken links detected" >> "$OUTPUT_FILE"
fi

# 2. Validate PRD.md against current state
echo "📋 Validating PRD.md..."
echo "" >> "$OUTPUT_FILE"
echo "## PRD.md Validation" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

PRD_FILE="$DOCS_DIR/PRD.md"
if [ -f "$PRD_FILE" ]; then
    # Check if documented scripts exist
    while IFS= read -r script_name; do
        if [ -n "$script_name" ] && [ ! -f "$WORKSPACE/scripts/$script_name" ]; then
            log_issue "ERROR" "PRD documents script that doesn't exist: $script_name" "$PRD_FILE"
        fi
    done < <(grep -oE '[a-z]+-?[a-z]+\.sh' "$PRD_FILE" 2>/dev/null | grep -E '^(update|validate|backup|auto|run|manage|check|setup|create|weekly)' | sort -u || true)
    
    # Check if documented skills exist
    while IFS= read -r skill_name; do
        skill_path="$WORKSPACE/.agents/skills/$skill_name"
        if [ -n "$skill_name" ] && [ ! -d "$skill_path" ]; then
            log_issue "WARN" "PRD documents skill that may not exist: $skill_name" "$PRD_FILE"
        fi
    done < <(grep -oE '\*\*[a-z]+-[a-z]+\*\*' "$PRD_FILE" 2>/dev/null | sed 's/\*\*//g' | sort -u || true)
    
    echo "✅ PRD.md validation complete" >> "$OUTPUT_FILE"
else
    log_issue "ERROR" "PRD.md not found" "$DOCS_DIR"
fi

# 3. Check for outdated references
echo "📋 Checking for outdated references..."
echo "" >> "$OUTPUT_FILE"
echo "## Outdated Reference Check" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Check for TODO/FIXME markers
TODO_COUNT=0
for md_file in $(find "$WORKSPACE" -name "*.md" -type f 2>/dev/null | grep -v node_modules | grep -v .git); do
    todos=$(grep -c -E '(TODO|FIXME|XXX|HACK):' "$md_file" 2>/dev/null || echo "0")
    if [ "$todos" -gt 0 ]; then
        TODO_COUNT=$((TODO_COUNT + todos))
        echo "- $md_file: $todos TODO/FIXME markers" >> "$OUTPUT_FILE"
    fi
done

if [ $TODO_COUNT -gt 0 ]; then
    echo "" >> "$OUTPUT_FILE"
    echo "⚠️  Total TODO/FIXME markers found: $TODO_COUNT" >> "$OUTPUT_FILE"
else
    echo "✅ No TODO/FIXME markers found" >> "$OUTPUT_FILE"
fi

# 4. Validate scripts directory consistency
echo "📋 Checking scripts directory..."
echo "" >> "$OUTPUT_FILE"
echo "## Scripts Directory Check" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for script in "$WORKSPACE/scripts"/*.sh; do
    if [ -f "$script" ]; then
        # Check if script has execute permission
        if [ ! -x "$script" ]; then
            log_issue "WARN" "Script missing execute permission: $(basename "$script")" "$script"
        fi
        
        # Check for basic shell syntax
        if ! bash -n "$script" 2>/dev/null; then
            log_issue "ERROR" "Script has syntax errors: $(basename "$script")" "$script"
        fi
    fi
done

echo "✅ Scripts directory check complete" >> "$OUTPUT_FILE"

# 5. Check memory files for today
echo "📋 Checking memory files..."
echo "" >> "$OUTPUT_FILE"
echo "## Memory Files Check" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

TODAY=$(date +%Y-%m-%d)
TODAY_MEMORY="$MEMORY_DIR/$TODAY.md"
if [ ! -f "$TODAY_MEMORY" ]; then
    log_issue "WARN" "Today's memory file does not exist yet" "$TODAY_MEMORY"
else
    echo "✅ Today's memory file exists" >> "$OUTPUT_FILE"
fi

# Summary
echo "" >> "$OUTPUT_FILE"
echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "## Summary" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "- **Errors:** $ISSUES_FOUND" >> "$OUTPUT_FILE"
echo "- **Warnings:** $WARNINGS" >> "$OUTPUT_FILE"
echo "- **Status:** $([ $ISSUES_FOUND -eq 0 ] && echo "✅ PASS" || echo "❌ FAIL")" >> "$OUTPUT_FILE"

echo ""
echo "======================================"
echo "Validation complete!"
echo "Errors: $ISSUES_FOUND"
echo "Warnings: $WARNINGS"
echo "Report saved to: $OUTPUT_FILE"

# Exit with error if critical issues found
if [ $ISSUES_FOUND -gt 0 ]; then
    exit 1
fi

exit 0
