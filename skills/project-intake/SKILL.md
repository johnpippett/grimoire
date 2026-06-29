---
name: project-intake
description: Use when starting work in a local project, switching agents or models, or handling an unfamiliar repo or folder.
---

# Project Intake

Use this before acting inside a project. It works for any coding agent.

## Steps

1. Find the project root and local guidance: `AGENTS.md`, `README.md`,
   `skills/`, and `wiki/`.
2. Read only the guidance relevant to the task. Repo-local instructions win
   over global habits.
3. Check current state before editing: git branch/status when available,
   important config files, and existing docs.
4. Pick matching project skills from `skills/`. If none fit, use the default
   project rules.
5. Never print secrets. Ask before destructive git, machine-level, or
   security-sensitive changes.

## Output

Report the actual project state, what you changed, what you verified, and any
skipped project docs.
