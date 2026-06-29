---
name: grimoire-update
description: Use when a project change affects code, config, workflow, architecture, deployment, integration, debugging, or policy.
---

# Grimoire Update

Project knowledge stays beside the project. Use the repo-local `wiki/` before
central notes.

## Workflow

1. Inspect `wiki/README.md` and existing notes for the topic.
2. Update the existing note when one fits. Otherwise create the next decimal
   note in the right folder:
   - `10-19 Conversations & Decisions/11 Key Decisions/`
   - `10-19 Conversations & Decisions/12 Session Logs/`
   - `20-29 Implementation & Operations/21 Implementation Notes/`
   - `20-29 Implementation & Operations/22 Workflows/`
   - `30-39 Integrations & Tooling/31 Tool Configs/`
   - `30-39 Integrations & Tooling/32 Integration Notes/`
3. Keep the note short: what changed, why, how to verify, rollback notes when
   relevant.
4. Update `12.01 Session Log Index.md` for notable sessions.
5. In the final response, name the wiki file changed. If no note was needed,
   say why.

## Skip

Skip for trivial read-only inspection, direct answers, or formatting-only edits
that do not change project behavior.
