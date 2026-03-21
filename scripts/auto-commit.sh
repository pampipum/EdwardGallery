#!/bin/bash
# auto-commit.sh - Git Auto-Commit Script
# Checks for uncommitted changes, stages docs/logs, creates descriptive commits
# Runs every 6 hours or on-demand

set -e

WORKSPACE="/root/.openclaw/workspace"
LOGS_DIR="$WORKSPACE/logs"
MEMORY_DIR="$WORKSPACE/memory"

echo "📝 Auto-Commit Check - $(date)"
echo "=============================="
echo ""

# Check if we're in a git repository
if ! git -C "$WORKSPACE" rev-parse --git-dir > /dev/null 2>&1; then
    echo "⚠️  Not a git repository: $WORKSPACE"
    exit 0
fi

cd "$WORKSPACE"

# Check git status
CHANGES=$(git status --porcelain 2>/dev/null || true)

if [ -z "$CHANGES" ]; then
    echo "✅ No uncommitted changes"
    exit 0
fi

echo "📋 Uncommitted changes detected:"
echo "$CHANGES"
echo ""

# Initialize commit message
COMMIT_MSG="chore: automated documentation update

Changes detected:
"

# Categorize changes
DOCS_CHANGED=""
LOGS_CHANGED=""
MEMORY_CHANGED=""
OTHER_CHANGED=""

while IFS= read -r line; do
    # Skip empty lines
    [ -z "$line" ] && continue
    
    file=$(echo "$line" | sed 's/^?? /' | sed 's/^ M /' | sed 's/^M /' | awk '{print $2}')
    
    # Categorize by path
    if [[ "$file" =~ ^docs/ ]] || [[ "$file" =~ \.md$ ]]; then
        DOCS_CHANGED="$DOCS_CHANGED  - $file\n"
        git add "$file"
    elif [[ "$file" =~ ^logs/ ]]; then
        LOGS_CHANGED="$LOGS_CHANGED  - $file\n"
        git add "$file"
    elif [[ "$file" =~ ^memory/ ]]; then
        MEMORY_CHANGED="$MEMORY_CHANGED  - $file\n"
        git add "$file"
    else
        OTHER_CHANGED="$OTHER_CHANGED  - $file\n"
        # Don't auto-add other files - may be sensitive
    fi
done <<< "$CHANGES"

# Build commit message
if [ -n "$DOCS_CHANGED" ]; then
    COMMIT_MSG="$COMMIT_MSG\n📚 Documentation:\n$DOCS_CHANGED"
fi

if [ -n "$LOGS_CHANGED" ]; then
    COMMIT_MSG="$COMMIT_MSG\n📊 Logs:\n$LOGS_CHANGED"
fi

if [ -n "$MEMORY_CHANGED" ]; then
    COMMIT_MSG="$COMMIT_MSG\n🧠 Memory:\n$MEMORY_CHANGED"
fi

if [ -n "$OTHER_CHANGED" ]; then
    COMMIT_MSG="$COMMIT_MSG\n⚠️  Other (not staged):\n$OTHER_CHANGED"
fi

COMMIT_MSG="$COMMIT_MSG\n---\nAutomated commit by auto-commit.sh"

# Check if there are staged changes
STAGED=$(git diff --cached --name-only 2>/dev/null || true)

if [ -z "$STAGED" ]; then
    echo "✅ No changes to commit (other changes may be ignored)"
    exit 0
fi

echo "📝 Staged files:"
echo "$STAGED"
echo ""

# Check for GitHub credentials
PUSH_AVAILABLE=false
if [ -n "$GITHUB_TOKEN" ] || [ -n "$GH_TOKEN" ]; then
    PUSH_AVAILABLE=true
    echo "✅ GitHub credentials available"
elif git remote -v 2>/dev/null | grep -q "github.com"; then
    # Check if SSH keys are configured
    if ssh-add -l &>/dev/null || [ -f ~/.ssh/id_rsa ] || [ -f ~/.ssh/id_ed25519 ]; then
        PUSH_AVAILABLE=true
        echo "✅ SSH credentials available"
    else
        echo "⚠️  No GitHub credentials found - will commit but not push"
    fi
else
    echo "⚠️  No GitHub remote configured - will commit but not push"
fi

# Create commit
echo ""
echo "📝 Creating commit..."
git commit -m "$COMMIT_MSG" 2>&1 || {
    echo "⚠️  Commit failed (may be due to no changes after filtering)"
    exit 0
}

echo "✅ Commit created successfully"

# Push if credentials available
if [ "$PUSH_AVAILABLE" = true ]; then
    echo ""
    echo "📤 Pushing to remote..."
    
    # Get default branch
    DEFAULT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    
    if git push origin "$DEFAULT_BRANCH" 2>&1; then
        echo "✅ Pushed successfully"
    else
        echo "⚠️  Push failed - check credentials"
    fi
fi

echo ""
echo "=============================="
echo "Auto-commit complete!"

exit 0
