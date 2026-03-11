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
