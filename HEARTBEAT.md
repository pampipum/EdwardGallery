# HEARTBEAT.md

# Project paused by user on 2026-03-12.
# Keep heartbeat quiet to minimize token usage.
# Reply HEARTBEAT_OK unless explicitly reactivated by user.

## Alert Monitoring (Active)

Run alert checks 2x daily:
```bash
bash /root/.openclaw/workspace/scripts/check-alerts.sh
```

## Logging & Automation Systems

**Logs:** `/root/.openclaw/workspace/logs/system.log` (JSONL)

**Daily Reports (cron):**
- 03:00 - Backup assets (`backup-assets.sh`)
- 05:00 - Check OpenClaw updates (`update-openclaw.sh`)
- 06:00 - Validate documentation (`validate-docs.sh`)
- 07:00 - Morning review (`morning-review.sh`)
- 08:00 - Run auto-tests (`run-auto-tests.sh`)

**Every 6 hours:** Auto-commit to GitHub (`auto-commit.sh`)

**Docs:** 
- `/root/.openclaw/workspace/docs/logging-system.md`
- `/root/.openclaw/workspace/docs/automation-systems.md`
- `/root/.openclaw/workspace/docs/PRD.md`
- `/root/.openclaw/workspace/learnings.md`

If alerts detected:
1. Update `/root/.openclaw/workspace/memory/alert-state.json`
2. Notify via Discord #alerts channel
3. Escalate HIGH/CRITICAL to Telegram

Current alert status: See `/root/.openclaw/workspace/memory/alert-state.json`
