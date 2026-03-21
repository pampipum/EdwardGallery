# Automation Systems

**Last Updated:** 2026-03-19

This document describes the continuous documentation, automated update/testing, auto-commit, and backup systems implemented in this workspace.

---

## Overview

Automation is implemented via shell scripts in `/root/.openclaw/workspace/scripts/` and scheduled via `cron`.

Primary goals:
- Keep documentation accurate and consistent
- Detect broken docs/scripts early
- Maintain OpenClaw updates with changelog tracking
- Keep backups of non-code assets (docs/memory/logs/media)
- Reduce manual operational overhead

---

## Scripts

### 1) Documentation Validator
**Script:** `/scripts/validate-docs.sh`  
**Schedule:** daily at **06:00**

What it does:
- Scans `.md` files in the workspace
- Extracts markdown links and flags likely broken local links
- Validates `docs/PRD.md` against the current workspace state (scripts existence, skills)
- Checks scripts for executable bit and shell syntax
- Writes a daily report to:
  - `/memory/docs-validation-YYYY-MM-DD.md`

Manual run:
```bash
bash /root/.openclaw/workspace/scripts/validate-docs.sh
```

---

### 2) OpenClaw Update
**Script:** `/scripts/update-openclaw.sh`  
**Schedule:** daily at **05:00**

What it does:
- Fetches latest OpenClaw version from npm (`npm view openclaw version`)
- Compares to installed global version (`npm list -g openclaw`)
- If newer version exists:
  - Installs latest: `npm install -g openclaw@latest`
  - Attempts to fetch release changelog from GitHub Releases API
  - Restarts gateway: `openclaw gateway restart`
  - Writes report to:
    - `/memory/openclaw-update-YYYY-MM-DD.md`

Manual run:
```bash
bash /root/.openclaw/workspace/scripts/update-openclaw.sh
```

Notes:
- This script may require elevated permissions depending on how npm global installs are configured.

---

### 3) Automated Tests
**Script:** `/scripts/run-auto-tests.sh`  
**Schedule:** daily at **08:00**

What it does:
- Discovers shell scripts in `/scripts/` and runs `bash -n`
- Validates JSON files with `jq` if available, else Python
- Performs basic checks that markdown files are non-empty
- Produces report:
  - `/logs/test-results-YYYY-MM-DD.md`

Manual run:
```bash
bash /root/.openclaw/workspace/scripts/run-auto-tests.sh
```

---

### 4) Git Auto-Commit
**Script:** `/scripts/auto-commit.sh`  
**Schedule:** every **6 hours**

What it does:
- Checks for uncommitted changes
- Auto-stages:
  - `docs/**`, root `*.md` (including `learnings.md`)
  - `logs/**`
  - `memory/**`
- Avoids staging other files by default to reduce risk of committing sensitive data
- Creates a descriptive commit message summarizing changed files
- Pushes if credentials appear available (token env vars or SSH)

Manual run:
```bash
bash /root/.openclaw/workspace/scripts/auto-commit.sh
```

---

### 5) Backups
**Script:** `/scripts/backup-assets.sh`  
**Schedule:** daily at **03:00**

What it backs up (non-code assets):
- `memory/*.md`, `memory/*.json`
- `docs/*.md`
- `logs/*.log`, `logs/*.md` (last 30 days)
- PDFs and images in workspace (excluding `.git`, `node_modules`, `backups`)
- DB-ish files: `*.db`, `*.sqlite*`

Creates:
- `/backups/backup-YYYY-MM-DD.tar.gz`

Retention:
- Keeps last **14** daily backups locally

Upload options:
1. **Box** (preferred) if `BOX_ACCESS_TOKEN` is set
2. **rsync fallback** if `REMOTE_BACKUP_USER` and `REMOTE_BACKUP_HOST` are set

Dry run (required before first real run):
```bash
bash /root/.openclaw/workspace/scripts/backup-assets.sh --dry-run
```

Real run:
```bash
bash /root/.openclaw/workspace/scripts/backup-assets.sh
```

---

## Cron Configuration

Intended entries to add to `crontab`:
```cron
0 5 * * * /root/.openclaw/workspace/scripts/update-openclaw.sh >> /root/.openclaw/workspace/logs/openclaw-update.log 2>&1
0 6 * * * /root/.openclaw/workspace/scripts/validate-docs.sh >> /root/.openclaw/workspace/logs/docs-validation.log 2>&1
0 3 * * * /root/.openclaw/workspace/scripts/backup-assets.sh >> /root/.openclaw/workspace/logs/backup.log 2>&1
0 */6 * * * /root/.openclaw/workspace/scripts/auto-commit.sh >> /root/.openclaw/workspace/logs/auto-commit.log 2>&1
0 8 * * * /root/.openclaw/workspace/scripts/run-auto-tests.sh >> /root/.openclaw/workspace/logs/auto-tests.log 2>&1
```

After installing cron jobs, verify:
```bash
crontab -l
```

---

## Operational Notes

- Avoid committing secrets: ensure `.env`, key material, and tokens remain ignored by `.gitignore`.
- If Box uploads are desired, set `BOX_ACCESS_TOKEN` in the environment.
- For rsync backups, set:
  - `REMOTE_BACKUP_USER`
  - `REMOTE_BACKUP_HOST`
  - `REMOTE_BACKUP_PATH` (optional)

---

## Related Docs

- `/docs/PRD.md`
- `/learnings.md`
- `/docs/agent-credentials-playbook.md`
- `/scripts/check-required-secrets.sh`
