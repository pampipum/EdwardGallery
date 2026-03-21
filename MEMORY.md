# MEMORY.md

## Agent deployment / credential discovery
- When a task involves GitHub pushes, Vercel deploys, or sending project emails, agents should first discover available credentials and required variables from local workspace files before asking the user again.
- Check these files first:
  - `docs/agent-credentials-playbook.md`
  - `.env.example`
  - `scripts/check-required-secrets.sh`
- Expected behavior:
  - inspect those files
  - infer which secrets/variables are required
  - use already-configured environment variables when available
  - run `bash scripts/check-required-secrets.sh` before deploys when relevant
- Do not ask the user to repeat where GitHub, Vercel, or email credentials live if those files already provide the answer.
- Never store raw secrets in memory files or committed files.

## Discord project-channel workflow
- When AML asks for a new Discord project channel, create the channel, wire it into Discord/OpenClaw routing, and confirm when Albi can respond there.
- Project channels should use `docs/project-channel-workflow.md` plus `docs/projects/<project-slug>.md` for project-specific rules, PM guidance, and standard updates in the format: Status / Blockers / Next steps.

## Installed skills & capabilities
- **qmd** - Search markdown knowledge bases, notes, and documentation using QMD (llama.cpp based, CPU-only on this VPS).
- **agent-browser** - Browser automation via OpenClaw browser control server.
- **agentmail** - Email inbox management via AgentMail API.
- **web-design-guidelines** - UI design review and accessibility audits.
- **frontend-design** - Production-grade frontend interface creation.

## Environment configuration
- Agent Browser safety defaults: `AGENT_BROWSER_CONTENT_BOUNDARIES=1`, `AGENT_BROWSER_MAX_OUTPUT=50000`, `AGENT_BROWSER_DEFAULT_TIMEOUT=45000`.
- QMD/llama CPU mode: `NODE_LLAMA_CPP_GPU=off`, `NODE_LLAMA_CPP_LOG_LEVEL=error`.
- Model alias **5.4** → `openai-codex/gpt-5.4` in `agents.defaults.models`.
- `AGENTMAIL_API_KEY` configured in OpenClaw config; gateway restarted to apply.

## ACP / Codex notes
- ACP Paperclip project research thread started 2026-03-06: `research-beast/reports/acp-project-paperclip-2026-03-06T07-30Z.md`.
- Known issue: stale `codex-acp` helper processes can consume ACP runtime slots; clear when blocked.
- Codex quota/billing exhaustion (`UsageLimitExceeded`) observed 2026-03-13; Gemini ACP also unhealthy as fallback at that time.

## Active project channels (Discord)
- `website-redesign`
- `landing-page-redesign`
- `alphaarena-migration`
- `ai-audits`

## Security incidents
- **2026-03-13**: `alphaarena-migration/.env` with secrets (OpenAI, Gemini, Gmail app password, other API keys) was accidentally committed to workspace repo. Removed from tracking, added to `.gitignore`, amended commit, and pushed. **Follow-up required**: rotate all exposed secrets.
