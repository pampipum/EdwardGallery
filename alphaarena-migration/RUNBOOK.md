# AlphaArena Migration Runbook

## Current Runtime Shape

- Source code lives in `repo/`
- Durable runtime state lives in `state/`
- Backend LLM calls are now designed to use OpenClaw itself via the local CLI
- Dedicated OpenClaw agent: `alphaarena`
- Paper mode is the default and live execution is disabled

## Local Setup

From the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

## Core Commands

Run from:

```bash
/root/.openclaw/workspace/alphaarena-migration/repo
```

### Healthcheck

```bash
.venv/bin/python -m backend.openclaw_tasks healthcheck
```

### Fetch Current Prices

```bash
.venv/bin/python -m backend.openclaw_tasks fetch-prices
```

### Initialize A Paper Portfolio

```bash
.venv/bin/python -m backend.openclaw_tasks start-paper --pm-id pm1 --capital 10000
```

### Run Risk Check

```bash
.venv/bin/python -m backend.openclaw_tasks risk-check --pm-id pm1
```

### Run Weekly Report

```bash
.venv/bin/python -m backend.openclaw_tasks weekly-report --pm-id pm1
```

## State Locations

- portfolios: `/root/.openclaw/workspace/alphaarena-migration/state/portfolios`
- logs: `/root/.openclaw/workspace/alphaarena-migration/state/logs`
- reports: `/root/.openclaw/workspace/alphaarena-migration/state/reports`
- cache: `/root/.openclaw/workspace/alphaarena-migration/state/cache`
- briefings: `/root/.openclaw/workspace/alphaarena-migration/state/briefings`

## OpenClaw-Native LLM Notes

The backend now supports an `openclaw` provider.

That means PM reasoning can come from:

- `openclaw agent --agent main ...`

For this project, the preferred agent is:

- `openclaw agent --agent alphaarena ...`

instead of direct Gemini/OpenAI/OpenRouter SDK billing state.

Optional runtime knobs:

- `ALPHAARENA_OPENCLAW_THINKING=minimal|low|medium|high`
- `ALPHAARENA_OPENCLAW_TIMEOUT_SECONDS=600`

## Cron Activation Rule

Do not enable live cron jobs until:

1. a paper-only PM analysis completes successfully end to end
2. the OpenClaw-backed reasoning path is stable
3. healthcheck and fetch tasks pass repeatedly

When ready, use `openclaw cron add` rather than editing scheduler JSON by hand.
