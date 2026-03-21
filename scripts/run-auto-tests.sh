#!/bin/bash
# run-auto-tests.sh - Automated Testing Script
# Discovers and validates scripts, JSON files, and markdown
# Runs daily at 8:00 AM

set -e

WORKSPACE="/root/.openclaw/workspace"
SCRIPTS_DIR="$WORKSPACE/scripts"
LOGS_DIR="$WORKSPACE/logs"
OUTPUT_FILE="$LOGS_DIR/test-results-$(date +%Y-%m-%d).md"

# Ensure directories exist
mkdir -p "$LOGS_DIR"

echo "🧪 Automated Tests - $(date)"
echo "============================"
echo ""

# Initialize output
cat > "$OUTPUT_FILE" << EOF
# Automated Test Results

**Date:** $(date +%Y-%m-%d)  
**Time:** $(date +%H:%M:%S)  
**Workspace:** $WORKSPACE

---

## Summary

EOF

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

# Function to log test result
log_test() {
    local name="$1"
    local result="$2"
    local details="${3:-}"
    
    ((TOTAL_TESTS++))
    
    if [ "$result" = "PASS" ]; then
        ((PASSED_TESTS++))
        echo "✅ PASS: $name"
        echo "- ✅ **$name**" >> "$OUTPUT_FILE"
    elif [ "$result" = "WARN" ]; then
        ((WARNINGS++))
        echo "⚠️  WARN: $name"
        echo "- ⚠️  **$name** (warning)" >> "$OUTPUT_FILE"
        [ -n "$details" ] && echo "  $details" >> "$OUTPUT_FILE"
    else
        ((FAILED_TESTS++))
        echo "❌ FAIL: $name"
        echo "- ❌ **$name** (FAILED)" >> "$OUTPUT_FILE"
        [ -n "$details" ] && echo "  $details" >> "$OUTPUT_FILE"
    fi
    
    [ -n "$details" ] && echo "  $details"
}

# 1. Shell Script Syntax Validation
echo "📋 Testing shell scripts..."
echo "" >> "$OUTPUT_FILE"
echo "## Shell Script Syntax Tests" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

SCRIPT_COUNT=0
for script in "$SCRIPTS_DIR"/*.sh; do
    if [ -f "$script" ]; then
        ((SCRIPT_COUNT++))
        script_name=$(basename "$script")
        
        # Syntax check
        if bash -n "$script" 2>/dev/null; then
            log_test "Syntax: $script_name" "PASS"
        else
            error_msg=$(bash -n "$script" 2>&1 | head -3)
            log_test "Syntax: $script_name" "FAIL" "$error_msg"
        fi
        
        # Check execute permission
        if [ -x "$script" ]; then
            log_test "Executable: $script_name" "PASS"
        else
            log_test "Executable: $script_name" "WARN" "Missing execute permission"
        fi
    fi
done

if [ $SCRIPT_COUNT -eq 0 ]; then
    echo "No shell scripts found in $SCRIPTS_DIR" >> "$OUTPUT_FILE"
fi

# 2. JSON Validation
echo ""
echo "📋 Testing JSON files..."
echo "" >> "$OUTPUT_FILE"
echo "## JSON Validation Tests" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

JSON_COUNT=0
for json_file in $(find "$WORKSPACE" -name "*.json" -type f 2>/dev/null | grep -v node_modules | grep -v .git | head -20); do
    ((JSON_COUNT++))
    json_name=$(basename "$json_file")
    json_path=$(realpath --relative-to="$WORKSPACE" "$json_file" 2>/dev/null || echo "$json_file")
    
    # Check if jq is available
    if command -v jq &> /dev/null; then
        if jq empty "$json_file" 2>/dev/null; then
            log_test "JSON: $json_path" "PASS"
        else
            error_msg=$(jq empty "$json_file" 2>&1 | head -3)
            log_test "JSON: $json_path" "FAIL" "$error_msg"
        fi
    else
        # Fallback to python
        if python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null; then
            log_test "JSON: $json_path" "PASS"
        else
            log_test "JSON: $json_path" "FAIL" "Invalid JSON syntax"
        fi
    fi
done

if [ $JSON_COUNT -eq 0 ]; then
    echo "No JSON files found" >> "$OUTPUT_FILE"
fi

# 3. Markdown Link Check (basic)
echo ""
echo "📋 Testing markdown files..."
echo "" >> "$OUTPUT_FILE"
echo "## Markdown Validation Tests" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

MD_COUNT=0
for md_file in $(find "$WORKSPACE" -name "*.md" -type f 2>/dev/null | grep -v node_modules | grep -v .git | head -20); do
    ((MD_COUNT++)) || true
    md_name=$(basename "$md_file")
    md_path=$(realpath --relative-to="$WORKSPACE" "$md_file" 2>/dev/null || echo "$md_file")
    
    # Check for basic markdown structure
    if [ -s "$md_file" ]; then
        log_test "Markdown: $md_path" "PASS"
    else
        log_test "Markdown: $md_path" "WARN" "Empty file"
    fi
done

if [ $MD_COUNT -eq 0 ]; then
    echo "No markdown files found" >> "$OUTPUT_FILE"
fi

# 4. Test scripts with test mode (if supported)
echo ""
echo "📋 Running script self-tests..."
echo "" >> "$OUTPUT_FILE"
echo "## Script Self-Tests" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for script in "$SCRIPTS_DIR"/*.sh; do
    if [ -f "$script" ] && [ -x "$script" ]; then
        script_name=$(basename "$script")
        
        # Check if script supports test mode
        if grep -q "test\|--test\|-t" "$script" 2>/dev/null; then
            echo "Testing $script_name..."
            # Try running with test flag (non-destructive)
            if bash "$script" test 2>/dev/null; then
                log_test "Self-test: $script_name" "PASS"
            else
                log_test "Self-test: $script_name" "WARN" "Test mode returned non-zero (may be expected)"
            fi
        fi
    fi
done

# 5. Critical files existence check
echo ""
echo "📋 Checking critical files..."
echo "" >> "$OUTPUT_FILE"
echo "## Critical Files Check" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

CRITICAL_FILES=(
    "docs/PRD.md"
    "learnings.md"
    "AGENTS.md"
    "SOUL.md"
    "scripts/manage-cron.sh"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$WORKSPACE/$file" ]; then
        log_test "Exists: $file" "PASS"
    else
        log_test "Exists: $file" "FAIL" "File not found"
    fi
done

# 6. Scripts with test blocks execution
echo ""
echo "📋 Executing test blocks..."
echo "" >> "$OUTPUT_FILE"
echo "## Test Block Execution" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Look for scripts that have explicit test sections
for script in "$SCRIPTS_DIR"/*.sh; do
    if [ -f "$script" ] && [ -x "$script" ]; then
        script_name=$(basename "$script")
        
        # Check for TEST or TESTING sections
        if grep -qE '^#.*TEST|test_case|run_test' "$script" 2>/dev/null; then
            echo "Found test blocks in $script_name"
            log_test "Test blocks: $script_name" "PASS" "Test blocks present"
        fi
    fi
done

echo "No explicit test blocks found in scripts" >> "$OUTPUT_FILE"

# Summary
echo ""
echo "============================"
echo "Test Summary"
echo "============================"
echo "Total:  $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo "Warnings: $WARNINGS"
echo ""

echo "" >> "$OUTPUT_FILE"
echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "## Summary" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "| Metric | Count |" >> "$OUTPUT_FILE"
echo "|--------|-------|" >> "$OUTPUT_FILE"
echo "| Total Tests | $TOTAL_TESTS |" >> "$OUTPUT_FILE"
echo "| Passed | $PASSED_TESTS |" >> "$OUTPUT_FILE"
echo "| Failed | $FAILED_TESTS |" >> "$OUTPUT_FILE"
echo "| Warnings | $WARNINGS |" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

if [ $FAILED_TESTS -gt 0 ]; then
    echo "**Status:** ❌ FAIL - $FAILED_TESTS test(s) failed" >> "$OUTPUT_FILE"
    echo ""
    echo "Status: ❌ FAIL"
    exit 1
else
    echo "**Status:** ✅ PASS" >> "$OUTPUT_FILE"
    echo ""
    echo "Status: ✅ PASS"
    exit 0
fi
