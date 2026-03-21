# Project Scheduler Configuration

This document tracks all scheduled tasks, cron jobs, and automation workflows across the workspace.

## Current Cron Jobs

```bash
# View current crontab
crontab -l
```

### Active Jobs

| Schedule | Task | Project | Log File |
|----------|------|---------|----------|
| `*/15 * * * *` | Watchdog health check | OpenClaw | `/root/.openclaw/logs/watchdog.log` |
| `0 20 * * *` | OpenClaw daily job | scrapling-project | `data/cron.log` |
| `0 9 * * *` | Xiaomi price tracker | scrapling-project | `data/cron_xiaomi.log` |
| `0 7 * * 1-5` | Claude adoption job | scrapling-project | `data/claude_adoption.log` |

## Project-Specific Schedules

### ai-audits (Swiss AI Audit)

**Status:** ⏸️ Paused (per HEARTBEAT.md, user request 2026-03-12)

**Planned Cron Jobs:**

| Schedule | Task | Script | Purpose |
|----------|------|--------|---------|
| `0 8 * * 1` | Weekly lead fetch | `scripts/fetch-swiss-leads.mjs` | Gather Swiss business leads (tourism, wealth management, clinics, manufacturing) |
| `0 10 * * 3` | Weekly presentation critiques | `scripts/send-presentation-critique-email.mjs` | Send AI presentation review to prospects |

**Wrapper Scripts Needed:**
- `/root/.openclaw/workspace/ai-audits/scripts/run-lead-fetch.sh`
- `/root/.openclaw/workspace/ai-audits/scripts/run-critique-email.sh`

**Notes:**
- Lead fetch targets: Davos, Graubünden, Zürich, Bern
- Sectors: tourism, wealth management, private clinics, manufacturing KMUs
- Sources: search.ch, local.ch
- Respect Swiss data protection (nDSG/FADP)

### scrapling-project

**Status:** ✅ Active

**Current Jobs:**
- Daily OpenClaw job at 20:00 (Europe/Zurich)
- Xiaomi price tracker at 09:00 daily
- Claude adoption job at 07:00 weekdays

**Log Location:** `/root/workspace/projects/scrapling-project/data/`

### bwtec-navigation-kiosk

**Status:** 🚧 Development

**Planned Jobs:**
- Build/deploy checks
- Kiosk health monitoring

## Maintenance Windows

### Weekly Maintenance (Sunday 03:00)
- Log rotation
- Temp file cleanup
- Dependency updates check

### Monthly Maintenance (1st of month, 02:00)
- Full system health check
- Cron job audit
- Secret rotation reminder

## Deployment Windows

**Default:** Weekdays 09:00-17:00 (Europe/Zurich)
**Blackout:** Weekends, Swiss holidays, 22:00-07:00

**Approval Required:**
- Production deploys
- Database migrations
- Secret rotations
- Outreach campaigns

## Automation Workflows

### Heartbeat Checks
- Frequency: 2-4x daily
- Checks: email, calendar, mentions, weather
- Quiet hours: 23:00-08:00

### Project Status Reports
- Format: Status / Blockers / Next steps
- Channel: Discord project channels
- Trigger: On-demand or scheduled

## Credential & Secret Management

**Preflight Script:** `bash scripts/check-required-secrets.sh`

**Before Running Scheduled Tasks:**
1. Verify environment variables are set
2. Check API rate limits
3. Validate output directories exist
4. Ensure logging is configured

## Adding New Cron Jobs

1. Create wrapper script in project's `scripts/` directory
2. Test manually: `bash scripts/your-script.sh`
3. Add to crontab: `crontab -e`
4. Verify: `crontab -l`
5. Monitor logs for first execution

### Wrapper Script Template

```bash
#!/bin/bash
# run-your-task.sh - Wrapper for cron execution

set -e

PROJECT_DIR="/root/.openclaw/workspace/your-project"
cd "$PROJECT_DIR" || exit 1

# Export required environment
export YOUR_API_KEY="${YOUR_API_KEY:-}"
export NODE_ENV="production"

# Run the task
node scripts/your-task.mjs >> data/cron-your-task.log 2>&1
```

## Monitoring & Alerts

**Watch for:**
- Cron job failures (check logs daily)
- Disk space usage
- API rate limit errors
- Secret expiration

**Log Locations:**
- OpenClaw: `/root/.openclaw/logs/`
- Projects: `*/data/cron*.log`
- System: `/var/log/cron.log`

## Version History

- **2026-03-19:** Initial scheduler documentation created
- **2026-03-13:** AI Audits cron audit - no jobs configured, plan passed to channel
