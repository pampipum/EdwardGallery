# AlphaArena OpenClaw Cron Plan

This is the target OpenClaw scheduling plan after the backend is converted into task entrypoints.

Until the backend tasks exist, these jobs stay as design only.

## Principles

- Use isolated cron jobs for exact timing
- Keep jobs narrow and idempotent
- Keep paper mode enforced at runtime
- Separate healthchecks from heavy analysis work

## Planned Jobs

### 1. Backend Healthcheck

- Frequency: every 15 minutes
- Purpose: verify imports, config load, writable state paths, and provider reachability summary
- Output: status summary only

Suggested cron:

```json
{
  "name": "AlphaArena healthcheck",
  "schedule": { "kind": "cron", "expr": "*/15 * * * *", "tz": "Europe/London" },
  "sessionTarget": "isolated"
}
```

### 2. PM Risk Checks

- Frequency: every minute
- Purpose: update valuations and run paper-only exit/risk logic for active PMs
- Scope: active PMs only

Suggested cron:

```json
{
  "name": "AlphaArena PM risk checks",
  "schedule": { "kind": "cron", "expr": "* * * * *", "tz": "Europe/London" },
  "sessionTarget": "isolated"
}
```

### 3. Scheduled Market Analysis

- Frequency: weekdays at 09:40 and 15:45 US/Eastern
- Purpose: main structured PM analysis windows

Suggested cron:

```json
{
  "name": "AlphaArena scheduled market analysis",
  "schedule": { "kind": "cron", "expr": "40 9 * * 1-5", "tz": "US/Eastern" },
  "sessionTarget": "isolated"
}
```

```json
{
  "name": "AlphaArena scheduled market analysis 2",
  "schedule": { "kind": "cron", "expr": "45 15 * * 1-5", "tz": "US/Eastern" },
  "sessionTarget": "isolated"
}
```

### 4. Sentinel Analysis Sweep

- Frequency: hourly
- Purpose: lighter scan for conditions that justify an extra PM analysis pass

Suggested cron:

```json
{
  "name": "AlphaArena sentinel sweep",
  "schedule": { "kind": "cron", "expr": "0 * * * *", "tz": "US/Eastern" },
  "sessionTarget": "isolated"
}
```

### 5. Weekly Reports

- Frequency: Sunday 00:00 UTC
- Purpose: generate PM weekly reports in paper mode

Suggested cron:

```json
{
  "name": "AlphaArena weekly reports",
  "schedule": { "kind": "cron", "expr": "0 0 * * 0", "tz": "UTC" },
  "sessionTarget": "isolated"
}
```

## Activation Order

1. Healthcheck
2. Scheduled market analysis
3. Weekly reports
4. PM risk checks
5. Sentinel sweep

Do not activate minutely jobs until:

- paper-only mode is enforced
- task entrypoints exist
- state writes are redirected into this workspace
- one manual end-to-end paper run passes
