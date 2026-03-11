# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

## Agent Deployment Bootstrap

For deploy-capable projects, agents should discover and use:

- `docs/agent-credentials-playbook.md`
- `.env.example`
- `scripts/check-required-secrets.sh`

This also applies to GitHub pushes, Vercel deploys, and project email tasks.
Agents should check those files before asking where credentials live, use configured environment variables when available, and avoid making the user repeat credential locations if the workspace already documents them.

Quick preflight:

```bash
bash scripts/check-required-secrets.sh
```

### Email sending note (Albi)

Albi is allowed to send project emails as often as needed, provided SMTP credentials are configured securely via environment variables.

## Installed Skills

### web-design-guidelines

Use for:
- web and landing page design direction
- layout, hierarchy, visual clarity, and presentation quality
- cleaner, more modern website structure and UX decisions

### frontend-design

Use for:
- frontend polish and design-oriented implementation work
- component-level UI improvements
- improving clarity, usability, and overall visual quality in frontends

---

Add whatever helps you do your job. This is your cheat sheet.
