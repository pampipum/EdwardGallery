#!/usr/bin/env bash
set -euo pipefail

required=(
  GITHUB_TOKEN
  VERCEL_TOKEN
  VERCEL_ORG_ID
  VERCEL_PROJECT_ID
)

missing=0
for k in "${required[@]}"; do
  if [[ -z "${!k:-}" ]]; then
    echo "Missing: $k"
    missing=1
  fi
done

if [[ "$missing" -eq 1 ]]; then
  echo "\nOne or more required secrets are missing."
  echo "Load them from your secret manager before deploy/push."
  exit 1
fi

echo "All required deploy secrets are present."
