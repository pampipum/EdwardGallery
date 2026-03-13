# Project Channel Workflow

Use this workflow for every new project channel or project ACP thread.

## Purpose

Each project should have:
- a dedicated Discord project channel
- a clear owner/context
- project-specific rules and PM guidance
- a standard update format
- an easy way to ask for progress without re-explaining the setup

## Default structure

For each project, create or maintain:
- a Discord channel named after the project
- a short channel topic
- a project brief file in the workspace
- optional ACP session/thread for deep execution work

## Project brief template

Create a file at:

`docs/projects/<project-slug>.md`

Template:

```md
# <Project Name>

## Goal
- What the project is trying to achieve

## PM / Owner
- Who is driving it
- Who can approve major changes

## Rules
- Project-specific constraints
- Safety / compliance / brand rules
- What must never be done without explicit approval

## Working mode
- research / implementation / design / audit / migration

## Update format
### Status
- current state in 1-3 bullets

### Blockers
- what is blocked
- what is missing
- what needs approval

### Next steps
- next 1-5 concrete actions

## Deliverables
- expected outputs/files/reports

## Notes
- links, references, channel ids, session keys
```

## Standard update format

When asked for updates, respond in this structure:

### Status
- concise summary of what has been done

### Blockers
- anything preventing progress
- approvals/credentials/bugs if relevant

### Next steps
- the next few concrete tasks

Keep updates short by default unless a detailed report is requested.

## Required behavior for agents

When working inside a project:
1. check whether `docs/projects/<project-slug>.md` exists
2. follow that file’s rules first
3. use the standard update format unless the user asks otherwise
4. if the project has a PM/owner rule, consult that before major actions
5. do not send outreach or external messages unless the project rules explicitly allow it and the user approved it

## New project setup checklist

When AML asks for a new project channel:
1. create the Discord channel
2. wire Albi/OpenClaw into it
3. create `docs/projects/<project-slug>.md`
4. populate goal / PM / rules / deliverables / update format
5. confirm the channel is ready

## Suggested prompt for users

Examples:
- `new project: ai-audits | PM: AML | goal: sell Swiss AI audits`
- `create project channel landing-page-redesign | PM: AML | rules: no live deploy without approval`
- `status update for ai-audits`
- `show blockers for landing-page-redesign`

## Notes

If a project already has its own repo-level rules, README, or PM doc, those should be referenced from the project brief and treated as canonical for project-specific decisions.
