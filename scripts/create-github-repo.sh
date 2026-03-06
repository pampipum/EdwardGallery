#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   GITHUB_TOKEN=... ./scripts/create-github-repo.sh <name> [public|private] [owner]
# Examples:
#   GITHUB_TOKEN=... ./scripts/create-github-repo.sh my-new-repo private
#   GITHUB_TOKEN=... ./scripts/create-github-repo.sh my-new-repo public aml6773

NAME="${1:-}"
VISIBILITY="${2:-private}"
OWNER="${3:-}"

if [[ -z "$NAME" ]]; then
  echo "Usage: GITHUB_TOKEN=... $0 <name> [public|private] [owner]"
  exit 1
fi

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Missing GITHUB_TOKEN env var"
  exit 1
fi

if [[ "$VISIBILITY" != "public" && "$VISIBILITY" != "private" ]]; then
  echo "Visibility must be public or private"
  exit 1
fi

PRIVATE=true
if [[ "$VISIBILITY" == "public" ]]; then
  PRIVATE=false
fi

if [[ -z "$OWNER" ]]; then
  # personal account repo
  API_URL="https://api.github.com/user/repos"
else
  # org repo
  API_URL="https://api.github.com/orgs/${OWNER}/repos"
fi

PAYLOAD=$(cat <<JSON
{
  "name": "$NAME",
  "private": $PRIVATE,
  "auto_init": true,
  "description": "Created by OpenClaw"
}
JSON
)

RESPONSE=$(curl -sS -X POST "$API_URL" \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d "$PAYLOAD")

HTML_URL=$(echo "$RESPONSE" | sed -n 's/.*"html_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)
CLONE_URL=$(echo "$RESPONSE" | sed -n 's/.*"clone_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)
MESSAGE=$(echo "$RESPONSE" | sed -n 's/.*"message"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)

if [[ -n "$HTML_URL" ]]; then
  echo "✅ Repo created: $HTML_URL"
  echo "Clone URL: $CLONE_URL"
  exit 0
fi

echo "❌ GitHub API error"
[[ -n "$MESSAGE" ]] && echo "Message: $MESSAGE"
echo "$RESPONSE"
exit 2
