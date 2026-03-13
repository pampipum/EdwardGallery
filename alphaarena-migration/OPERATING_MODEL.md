# AlphaArena OpenClaw Operating Model

## Target Runtime Shape

The migrated project should run as a set of callable backend tasks, not as one monolithic always-on FastAPI process that owns its own schedulers.

OpenClaw should own:

- when jobs run
- what task each run performs
- how failures are retried and reported
- how project continuity is recorded

The Python backend should own:

- data fetching
- market analysis
- portfolio state transitions
- paper execution simulation
- report generation

## Target Components

### 1. Config Layer

- `config/runtime.json` or equivalent project config
- environment variables only for secrets and machine-specific toggles
- explicit `paper_only: true` safety flag

### 2. State Layer

- `state/portfolios/`
- `state/reports/`
- `state/cache/`
- `state/logs/`

All repo writes should be redirected here.

### 3. Task Layer

- `task_fetch_market_data`
- `task_run_pm_analysis(pm_id)`
- `task_run_risk_checks(pm_id)`
- `task_generate_weekly_report(pm_id)`
- `task_healthcheck`

Each task should be runnable directly by OpenClaw.

### 4. API Layer

Keep a slim API only after task execution is stable.
The API is not the first milestone.

## Runtime Safety Changes Required

- remove startup auto-resume behavior
- remove startup-triggered analysis side effects
- remove in-process APScheduler ownership
- block executor factory from returning live executors
- quarantine live Kraken test code

## Success Criteria

- all configured assets fetch successfully in paper mode
- each PM can run analysis without live broker access
- portfolio JSON state updates cleanly under OpenClaw-managed tasks
- cron-driven operation survives transient provider failures
- logs and reports are inspectable from this workspace

## Failure Handling

- retries with exponential backoff for provider errors
- no crash loops on single-provider failure
- clear healthcheck output
- daily project heartbeat to catch drift, stalled jobs, or broken credentials
