# Project Scheduler - Setup Complete

**Date:** 2026-03-19  
**Status:** ✅ Infrastructure ready, awaiting user approval to activate

## What Was Created

### Documentation
- `/root/.openclaw/workspace/docs/scheduling.md` - Master scheduling configuration

### Scripts
- `/root/.openclaw/workspace/scripts/setup-cron-jobs.sh` - Install cron jobs
- `/root/.openclaw/workspace/scripts/manage-cron.sh` - View/manage cron jobs
- `/root/.openclaw/workspace/scripts/weekly-maintenance.sh` - Weekly maintenance tasks
- `/root/.openclaw/workspace/ai-audits/scripts/run-lead-fetch.sh` - Lead fetch wrapper
- `/root/.openclaw/workspace/ai-audits/scripts/run-critique-email.sh` - Critique email wrapper

## Current Cron Jobs (Active)

```
*/15 * * * *   - OpenClaw watchdog (health check every 15 min)
0 20 * * *     - scrapling-project OpenClaw daily job (20:00 Europe/Zurich)
0 9 * * *      - scrapling-project Xiaomi price tracker (09:00 daily)
0 7 * * 1-5    - scrapling-project Claude adoption job (07:00 weekdays)
```

## Proposed New Jobs (Ready to Install)

### AI Audits Project
**Note:** Currently paused per user request (HEARTBEAT.md, 2026-03-12)

| Schedule | Task | Command |
|----------|------|---------|
| `0 8 * * 1` | Weekly lead fetch | `cd /root/.openclaw/workspace/ai-audits && bash scripts/run-lead-fetch.sh` |
| `0 10 * * 3` | Weekly critique email | `cd /root/.openclaw/workspace/ai-audits && bash scripts/run-critique-email.sh` |

### Weekly Maintenance
| Schedule | Task | Command |
|----------|------|---------|
| `0 3 * * 0` | Weekly maintenance | `bash /root/.openclaw/workspace/scripts/weekly-maintenance.sh` |

## How to Use

### View Status
```bash
bash /root/.openclaw/workspace/scripts/manage-cron.sh status
```

### View Logs
```bash
# All logs
bash /root/.openclaw/workspace/scripts/manage-cron.sh logs

# Specific project
bash /root/.openclaw/workspace/scripts/manage-cron.sh logs ai-audits
```

### Install New Jobs (requires approval)
```bash
bash /root/.openclaw/workspace/scripts/setup-cron-jobs.sh
```

### Test Scripts Manually
```bash
bash /root/.openclaw/workspace/scripts/manage-cron.sh test ai-audits
```

### Remove Jobs
```bash
# Remove specific project
bash /root/.openclaw/workspace/scripts/manage-cron.sh remove ai-audits

# Remove all
bash /root/.openclaw/workspace/scripts/manage-cron.sh remove all
```

## Next Steps

1. **User approval needed** to activate AI Audits cron jobs (currently paused)
2. **Test scripts** before deploying: `bash manage-cron.sh test ai-audits`
3. **Set environment variables** for critique email:
   - `AGENTMAIL_API_KEY`
   - `CRITIQUE_EMAIL_RECIPIENT` (optional default)
4. **Monitor logs** after first execution

## Maintenance Schedule

- **Weekly:** Sunday 03:00 - Log rotation, temp cleanup, health checks
- **Monthly:** 1st of month 02:00 - Full audit, secret rotation reminder
- **Deployment windows:** Weekdays 09:00-17:00 Europe/Zurich (approval required)

## Security Notes

- All scripts use absolute paths
- Logs capture errors for debugging
- Environment variables required for email sending
- No external outreach without explicit approval (per ai-audits project rules)
