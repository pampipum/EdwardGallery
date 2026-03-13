# AlphaArena OpenClaw Migration Scope

## Objective

Rebuild AlphaArena as an OpenClaw-operated backend service that runs safely in paper mode, fetches market and AI inputs reliably, and can be supervised through OpenClaw-native scheduling and workspace state.

This is not a lift-and-shift VPS deployment.
This is an OpenClaw-first operating redesign.

## In Scope

- Backend-only migration first
- Paper trading only
- Data fetching, analysis, PM orchestration, portfolio state, reporting
- OpenClaw-native scheduling via cron jobs and project heartbeat
- File/path normalization for OpenClaw workspace operation
- Dependency cleanup and runtime hardening
- Test and validation flow that proves data fetches and PM loops work without live execution

## Out of Scope For Phase 1

- Live trading
- Kraken live execution
- Autonomous financial execution
- Frontend parity
- VPS/Nginx/systemd deployment
- Email delivery unless explicitly requested later

## Non-Negotiable Safety Rules

- Force paper mode globally
- Remove all default live execution paths from startup
- Disable auto-resume of any prior live-capable PM state
- Exclude live broker tests from default execution
- Treat all external broker actions as blocked until explicit user confirmation

## OpenClaw Strengths We Will Design Around

- Isolated cron jobs that can wake the agent on exact schedules
- Project-local heartbeat instructions for continuity and quiet supervision
- Workspace file state as durable memory
- Shared credentials/environment injection where already configured
- Strong fit for long-running orchestration, scheduled checks, and iterative migration work

## Phase Definition

### Phase 1: Safe Backend Foundation

- Import the source code into this workspace
- Lock the system to paper mode
- Normalize config, paths, logs, reports, and portfolio state
- Make data fetches and AI analysis run reliably

### Phase 2: OpenClaw Runtime Conversion

- Replace in-process scheduling assumptions with OpenClaw cron ownership
- Split work into callable tasks
- Make PM analysis, risk checks, and weekly reports idempotent

### Phase 3: Validation And Optimization

- Verify all providers needed for paper mode
- Add mocks/fallbacks where providers are brittle
- Tune schedules, retries, and logging
- Prove the backend can run unattended in OpenClaw

### Phase 4: Optional Surface Area

- Reintroduce frontend if useful
- Consider email/report delivery
- Revisit live execution only by explicit user request
