# Agent Credentials Playbook (Secure)

This project is configured so agents can deploy/push **without storing raw secrets in memory files**.

## 1) Required secrets (set as environment variables)

- `GITHUB_TOKEN` → GitHub PAT with repo permissions
- `VERCEL_TOKEN` → Vercel token
- `VERCEL_ORG_ID` → Vercel org/team id
- `VERCEL_PROJECT_ID` → Vercel project id
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` (only if email sending is automated)
- `MAIL_FROM` and optional default `MAIL_TO`

## 2) Where to keep them

Use one of these secure stores:

- Host-level env vars (systemd/docker/CI secret store)
- Password manager + runtime injection
- Vault/Secrets manager

Avoid putting secrets in:

- `MEMORY.md`
- `memory/*.md`
- committed files
- chat messages

## 3) Runtime check command

```bash
bash scripts/check-required-secrets.sh
```

## 4) Typical workflow

1. Export/inject env vars
2. Run secret check
3. Push to GitHub
4. Deploy to Vercel
5. Send summary email using SMTP creds (optional)

## 5) Non-secret identity config

Safe to store in memory/docs:

- GitHub username/org
- default repo naming pattern
- Vercel project naming convention
- preferred sender display name

Do not store passwords/tokens/API keys in memory files.

## 6) Agent email capability note (Albi)

Albi can send project emails/updates as often as needed **when email credentials are configured** (`SMTP_*`, `MAIL_FROM`).

Default sender identity:
- `MAIL_FROM=albi@agentmail.to`

Recommended policy:
- Sending frequency: unlimited as needed for project operations
- Keep emails concise and professional unless user asks otherwise
- Always include deployment links/status and next actions when relevant
