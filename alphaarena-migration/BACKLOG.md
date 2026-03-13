# AlphaArena Migration Backlog

## Status Legend

- `todo`
- `doing`
- `blocked`
- `done`

## Workstreams

### A. Repository Ingestion

- `done` Clone/import the private source repo into this workspace
- `doing` Mark the active runtime paths and archive duplicate legacy trees
- `todo` Record the chosen target directory layout

### B. Safety Lockdown

- `done` Force global paper mode
- `done` Remove `pm6` live execution path from active runtime
- `done` Disable auto-resume on startup
- `todo` Exclude `test_kraken_live.py` from default test runs
- `done` Add explicit safety guard that refuses live executors

### C. Runtime Refactor

- `done` Extract callable task entrypoints for fetch, analyze, risk-check, report
- `doing` Replace local scheduler assumptions with OpenClaw cron ownership
- `done` Move stateful writes into `state/`
- `done` Normalize logs, reports, and cache files

### D. Dependency Cleanup

- `done` Build accurate backend dependency list
- `done` Add missing imports used in code such as `requests` and `pytz`
- `todo` Resolve `pandas_ta` vs `pandas-ta-classic` ambiguity
- `todo` identify undocumented external CLI dependencies and remove or stub them for paper mode

### E. Provider Validation

- `done` Verify Yahoo/yfinance data flow
- `todo` Verify Alpha Vantage flow and cache behavior
- `todo` Verify FMP flow
- `todo` Verify sentiment/fear-greed flow
- `doing` Verify LLM provider fallback behavior for paper analysis

### F. Testing

- `doing` Build paper-only smoke test suite
- `todo` Add fixture-driven portfolio state tests
- `done` Add task-level healthcheck command
- `doing` Prove that each PM runs without broker access

### G. OpenClaw Operations

- `done` Add project-local heartbeat instructions
- `done` Define isolated cron jobs for healthcheck, PM analysis, risk checks, and weekly reports
- `done` Add runbook for stalled jobs and provider failures

## Immediate Priority Order

1. Safety lockdown
2. Repo ingestion
3. Runtime refactor
4. Dependency cleanup
5. Provider validation
6. Cron activation
