# Logging System (System + Agent Actions + Morning Review)

This workspace includes a lightweight, structured logging pipeline for:
- **System events / cron jobs / alerts**
- **Agent actions** (sessions, tool calls, sub-agent spawns)
- **Daily 07:00 morning review** that summarizes the last 24h and proposes fixes

All logs are **JSONL** (one JSON object per line) to keep things fast and easy to parse with `jq`.

## Paths

- System log (JSONL):
  - `/root/.openclaw/workspace/logs/system.log`
- Morning review report (markdown):
  - `/root/.openclaw/workspace/memory/morning-review-YYYY-MM-DD.md`
- Morning review cron stdout/stderr log:
  - `/root/.openclaw/workspace/logs/morning-review.log`

Scripts:
- `/root/.openclaw/workspace/scripts/log-system.sh`
- `/root/.openclaw/workspace/scripts/log-agent-action.sh`
- `/root/.openclaw/workspace/scripts/morning-review.sh`

## Event schema (JSONL)

Each line in `system.log` is:

```json
{
  "timestamp": "2026-03-19T10:51:00Z",
  "epoch": "1773917460",
  "event_type": "CRON_JOB",
  "severity": "INFO",
  "source": "check-alerts",
  "message": "Alert check started",
  "context": {"job": "..."}
}
```

### Event types

- `SYSTEM_START`
- `SYSTEM_ERROR`
- `AGENT_ACTION`
- `CRON_JOB`
- `API_CALL`
- `DEPLOY`
- `ALERT`

### Severities

- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

## 1) System logging: `log-system.sh`

### Log an event

```bash
bash scripts/log-system.sh log SYSTEM_START INFO scheduler "System initialized" '{"version":"1"}'
```

### Rotate logs (keep last 7 days)

```bash
bash scripts/log-system.sh rotate
```

### Quick queries

```bash
bash scripts/log-system.sh tail 20
bash scripts/log-system.sh count 24
bash scripts/log-system.sh get ALERT CRITICAL 48
```

## 2) Agent action logging: `log-agent-action.sh`

This script logs into `system.log` using `log-system.sh`.

Examples:

```bash
bash scripts/log-agent-action.sh session-start sess_123 main '{"channel":"telegram"}'
bash scripts/log-agent-action.sh tool-call sess_123 browser 1500 true
bash scripts/log-agent-action.sh subagent-spawn sess_123 sub_456 "Research task"
bash scripts/log-agent-action.sh session-end sess_123 120000 true

bash scripts/log-agent-action.sh stats 24
```

### How to integrate with OpenClaw session events

OpenClaw does not currently auto-hook every tool call into custom scripts, so the integration is **wrapper-based**:

- If you have a long-running script that runs agent actions, add log calls at:
  - start/end of the script
  - before/after each tool call (or external command)
  - on errors/exit traps

Pattern:

```bash
SESSION_ID="sess_$(date +%s)"
START_MS=$(date +%s%3N)

bash scripts/log-agent-action.sh session-start "$SESSION_ID" main '{"job":"weekly-maintenance"}'

# ... do work ...

END_MS=$(date +%s%3N)
DUR=$((END_MS-START_MS))

bash scripts/log-agent-action.sh session-end "$SESSION_ID" "$DUR" true
```

## 3) Morning Review: `morning-review.sh`

- Reads the previous **24 hours** from `logs/system.log`
- Filters for `ERROR`, `CRITICAL`, and `ALERT`
- Generates a markdown report into `memory/`
- Prepares a Discord-ready summary message when issues look **critical**

Run manually:

```bash
bash scripts/morning-review.sh
```

### Discord notification

Because subagents should not send external messages directly, the script **prepares** a message at:

- `/root/.openclaw/workspace/memory/alerts/discord-critical-YYYY-MM-DD.txt`

Main agent (or a Discord-enabled automation) can post that to `#alerts`.

## Cron job

Install this line in root crontab:

```cron
0 7 * * * /root/.openclaw/workspace/scripts/morning-review.sh >> /root/.openclaw/workspace/logs/morning-review.log 2>&1
```

Verify:

```bash
crontab -l | grep morning-review.sh
```

## Privacy / safety

- Keep `context` fields **lightweight**.
- Do **not** log secrets (API keys, tokens, credentials, full request payloads).
- Prefer redacting or hashing identifiers if unsure.
