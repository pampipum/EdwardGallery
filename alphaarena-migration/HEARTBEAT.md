# AlphaArena Migration Heartbeat

This project is backend-first and paper-only.

Hard rules:

- Never enable live trading
- Never run broker-connected execution
- Never run live Kraken tests
- Never treat prior portfolio JSON state as permission to resume autonomous trading

On heartbeat:

1. Check whether the migration workspace now contains the source repo files.
2. Check whether paper-only safety changes have been implemented.
3. Check whether task entrypoints exist for:
   - healthcheck
   - market fetch
   - PM analysis
   - risk checks
   - weekly reports
4. Check whether OpenClaw cron specs have been prepared for the backend.
5. Check whether the project backlog needs status updates.
6. Append important continuity notes to a daily memory file if the repo changed meaningfully.

Reach out only when:

- a blocker prevents safe paper-mode progress
- credentials required for paper-mode data fetching are missing
- the repo has been imported and is ready for implementation
- the backend is running in paper mode and ready for validation

If nothing material changed, reply `HEARTBEAT_OK`.
