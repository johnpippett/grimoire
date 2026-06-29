# Project Wiki

This repo keeps durable project documentation in decimal-numbered markdown files.
Use it as the canonical record of what changed, why, and how to verify it.

## Numbering

- `10-19 Conversations & Decisions/`
  - `11 Key Decisions/`
  - `12 Session Logs/`
- `20-29 Implementation & Operations/`
  - `21 Implementation Notes/`
  - `22 Workflows/`
- `30-39 Integrations & Tooling/`
  - `31 Tool Configs/`
  - `32 Integration Notes/`
- `90-99 Archive/`
  - historical notes and retired scripts

File names use decimal numbers:

- `11.01 Project Documentation Policy.md`
- `12.01 Session Log Index.md`
- `21.01 Initial Architecture Decisions.md`
- `22.01 Local Development Workflow.md`
- `31.01 MCP Server Configuration.md`

Use the next available number in the most relevant folder. Prefer updating an
existing note when the topic already exists.

## Agent Rule

Any agent making meaningful project changes must create or update a wiki
note. Each note should cover:

- what changed
- why it changed
- how to verify it
- rollback notes, when relevant

If no wiki update is needed, the agent must say why in its final response.
