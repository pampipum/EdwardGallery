# Product Requirements Document (PRD)

**Last Updated:** 2026-03-19  
**Version:** 1.0  
**Maintainer:** OpenClaw Agent

---

## Overview

This document maps all capabilities, tools, integrations, and operational boundaries of the OpenClaw workspace. It serves as the single source of truth for what this agent system can do.

---

## 1. Core Capabilities

### 1.1 File Operations
- **read**: Read text files and images (jpg, png, gif, webp) with offset/limit support
- **write**: Create or overwrite files, auto-creates parent directories
- **edit**: Precise text replacement in files (exact match required)

### 1.2 Web & Network
- **web_search**: Search the web using Brave Search API (region-specific, localized)
- **web_fetch**: Extract readable content from URLs (HTML → markdown/text)
- **browser**: Full browser automation (navigate, click, type, screenshot, data extraction)

### 1.3 System & Process
- **exec**: Execute shell commands with background continuation, PTY support
- **process**: Manage running exec sessions (list, poll, log, write, send-keys, kill)

### 1.4 Messaging & Communication
- **message**: Send/manage messages via channel plugins (Telegram, Discord, Signal)
- **tts**: Convert text to speech (audio delivered automatically)

### 1.5 Visual Analysis
- **image**: Analyze images with vision model (single or multiple, up to 20)
- **pdf**: Analyze PDF documents (native or text extraction, up to 10 files)
- **canvas**: Control node canvases (present, navigate, eval, snapshot)

### 1.6 Agent Management
- **sessions_yield**: End current turn, receive subagent results
- **Subagents**: Spawn descendant agents for parallel task execution

### 1.7 ACP Runtime
- ACP (Agent Communication Protocol) runtime sessions
- Direct acpx-driven sessions ("telephone game" flow)
- Coding-agent thread management via `sessions_spawn`

---

## 2. Installed Skills

| Skill | Source | Description |
|-------|--------|-------------|
| **frontend-design** | anthropics/skills | Create distinctive, production-grade frontend interfaces with high design quality |
| **skill-creator** | anthropics/skills | Create, modify, and optimize skills; run evals and benchmark performance |
| **web-design-guidelines** | vercel-labs/agent-skills | Review UI code for Web Interface Guidelines compliance |

### Skill Locations
- `~/.openclaw/workspace/.agents/skills/frontend-design/`
- `~/.openclaw/workspace/.agents/skills/skill-creator/`
- `~/.openclaw/workspace/.agents/skills/web-design-guidelines/`

---

## 3. Tools Available

| Tool | Category | Description |
|------|----------|-------------|
| `read` | File I/O | Read file contents (text/images) |
| `write` | File I/O | Create/overwrite files |
| `edit` | File I/O | Precise text replacement |
| `exec` | System | Run shell commands |
| `process` | System | Manage background sessions |
| `browser` | Web | Browser automation |
| `canvas` | Visual | Canvas control/snapshot |
| `message` | Communication | Send/manage messages |
| `sessions_yield` | Agent | End turn, receive results |
| `web_search` | Web | Brave Search API |
| `web_fetch` | Web | URL content extraction |
| `image` | Visual | Image analysis |
| `pdf` | Visual | PDF analysis |
| `tts` | Communication | Text-to-speech |

---

## 4. Project Channels

### Discord (via message tool)
- Channel operations: create, edit, delete, move
- Member management: info, permissions, roles
- Content: send, edit, delete, pin, react, poll
- Threads: create, list, reply
- Events: create, list
- Media: emoji, stickers, uploads

### Telegram (current channel)
- Send/edit/delete messages
- Reactions (minimal mode)
- Topics/threads
- Polls

### Signal (configured)
- Send messages
- Reactions

---

## 5. Cron Jobs

| Schedule | Script | Purpose | Log |
|----------|--------|---------|-----|
| `*/15 * * * *` | watchdog.sh | System health monitoring | `/root/.openclaw/logs/watchdog.log` |
| `0 20 * * *` | run_openclaw_job.sh | Scrapling project jobs | `scrapling-project/data/cron.log` |
| `0 9 * * *` | xiaomi_price_tracker.py | Price tracking | `scrapling-project/data/cron_xiaomi.log` |
| `0 7 * * 1-5` | run_claude_adoption_job.sh | Claude adoption (weekdays) | `scrapling-project/data/claude_adoption.log` |

### Planned Automation (to be installed)
| Schedule | Script | Purpose |
|----------|--------|---------|
| `0 5 * * *` | update-openclaw.sh | Daily OpenClaw updates |
| `0 6 * * *` | validate-docs.sh | Documentation validation |
| `0 3 * * *` | backup-assets.sh | Daily backups |
| `0 */6 * * *` | auto-commit.sh | Git auto-commit |
| `0 8 * * *` | run-auto-tests.sh | Automated testing |

---

## 6. Integrations

### 6.1 AgentMail
- AI agent email inboxes
- Send/receive emails programmatically
- Attachment handling
- Labels and organization
- Webhook/real-time notifications
- Multi-tenant isolation with pods

### 6.2 OpenClaw Gateway
- Gateway daemon management (start/stop/restart/status)
- Node connection and pairing
- Remote access via VPS/tailnet
- Plugin system

### 6.3 Discord
- Full bot API access
- Channel/category management
- Member/role permissions
- Events, polls, reactions
- Media uploads (emoji, stickers)

### 6.4 Telegram
- Bot messaging
- Group chat participation
- Topics/threads support
- Reactions (minimal mode)

### 6.5 GitHub
- Repository operations via CLI/API
- Push/pull with credentials from env vars
- Credential discovery via `docs/agent-credentials-playbook.md`

### 6.6 Vercel
- Deployment automation
- Project management
- Credential discovery via workspace playbook

---

## 7. Security Boundaries

### 7.1 Approval Required
- Destructive commands (rm, destructive edits)
- External communications (emails, tweets, public posts)
- Elevated permissions (sudo, system changes)
- Credential access outside documented paths

### 7.2 Rate Limits
- Assume rate limits on external API writes
- Prefer fewer larger writes over tight loops
- Serialize bursts when possible
- Respect 429/Retry-After responses

### 7.3 Credential Handling
- Never store raw secrets in committed files
- Use environment variables or secret manager
- Discovery path: `docs/agent-credentials-playbook.md` → `.env.example` → `scripts/check-required-secrets.sh`
- Run `bash scripts/check-required-secrets.sh` before deploy operations

### 7.4 Data Boundaries
- Private data stays private (no exfiltration)
- MEMORY.md only loaded in main sessions (not group chats)
- Sensitive files excluded via .gitignore
- Box API uses BOX_ACCESS_TOKEN from environment

### 7.5 Tool Approval Flow
- exec with approval-pending returns concrete `/approve` command
- allow-once: single command only
- allow-always: persistent permission
- Preserve full command/script for user review

---

## 8. Workspace Structure

```
/root/.openclaw/workspace/
├── docs/                    # Documentation
│   ├── PRD.md              # This file
│   ├── automation-systems.md
│   ├── agent-credentials-playbook.md
│   └── projects/           # Project-specific docs
├── scripts/                 # Automation scripts
├── skills/                  # Custom skills
├── memory/                  # Daily memory logs
├── logs/                    # Application logs
├── learnings.md            # Mistakes & lessons log
├── MEMORY.md               # Long-term memory
├── SOUL.md                 # Agent identity/persona
├── AGENTS.md               # Workspace conventions
├── TOOLS.md                # Local tool notes
├── USER.md                 # User preferences
├── IDENTITY.md             # Agent identity metadata
└── skills-lock.json        # Installed skills registry
```

---

## 9. Update Protocol

This PRD must be updated when:
- New tools are added to the system
- New skills are installed
- New cron jobs are scheduled
- New integrations are configured
- Security boundaries change
- Major capability changes occur

**Update Process:**
1. Edit this file with changes
2. Note the date and version
3. Run `validate-docs.sh` to verify consistency
4. Commit changes via `auto-commit.sh`

---

## 10. Related Documents

- `/docs/automation-systems.md` - Automation infrastructure documentation
- `/learnings.md` - Mistakes and lessons learned
- `/docs/agent-credentials-playbook.md` - Credential management
- `/scripts/check-required-secrets.sh` - Secret validation
- `/memory/YYYY-MM-DD.md` - Daily operational logs
