# GitHub Repo Creation (OpenClaw VPS)

## One-time setup
1. Add `GITHUB_TOKEN` to `/root/.openclaw/openclaw.json` under `env.vars`.
2. Restart gateway.

Recommended token scopes:
- Personal repos: `repo`
- Org repos: `repo` + org permissions as required

## Create repo command

```bash
GITHUB_TOKEN=... ./scripts/create-github-repo.sh <name> [public|private] [owner]
```

Examples:

```bash
# Personal private repo
GITHUB_TOKEN=... ./scripts/create-github-repo.sh my-new-repo private

# Personal public repo
GITHUB_TOKEN=... ./scripts/create-github-repo.sh my-new-repo public

# Org private repo
GITHUB_TOKEN=... ./scripts/create-github-repo.sh my-new-repo private my-org
```

## Notes
- Script auto-initializes repo with a README.
- If owner is omitted, repo is created on the token owner account.
- If API returns 422, the repo name usually already exists.
