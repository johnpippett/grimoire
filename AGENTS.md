# Project Instructions

## Default Behavior

- Be concise.
- Read before editing.
- Verify important claims with tools.
- Never print secrets.
- Ask before destructive git, machine-level, or security-sensitive changes.
- Do not commit, push, reset, release, or rewrite history unless explicitly asked.

## Scope

<!-- Customize this section for your project -->

This project is the canonical home for ...

## Wiki Documentation Gate

Agents working in this repo must maintain the project wiki in `wiki/` using the
decimal numbering system described in `wiki/README.md`.

Before editing:

- Inspect `wiki/` for relevant project context.
- Reuse or update existing notes when the topic already exists.

During meaningful work:

- Create or update a decimal-numbered markdown note for code, config, workflow,
  architecture, policy, dependency, integration, deployment, or debugging
  changes.
- Record what changed, why it changed, how to verify it, and rollback notes
  when rollback is relevant.
- Keep project-specific notes inside this repo's `wiki/`.

Before final response:

- Report which `wiki/` file was created or updated.
- If no wiki note was needed, explicitly say why.

Trivial read-only inspection, small formatting-only edits, and direct answers
that do not change project state may skip a wiki update, but the final response
must say that no project documentation changed.

## Project Skills

This repo has model-agnostic skills in `skills/`.
Before meaningful work, inspect `skills/README.md` and use any matching
`skills/<name>/SKILL.md`.
Treat these as repo-local guidance, not a wrapper or model-specific harness.
