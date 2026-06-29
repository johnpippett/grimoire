# Grimoire — Agent Project Library

Any coding agent working in this project must follow this file. It works with
Claude Code, Cursor, Copilot, Aider, OpenCode, Codex, and any other harness —
rename it to the convention your harness expects if needed (CLAUDE.md,
.cursorrules, .github/copilot-instructions.md, AIDER.md, etc.).

The decimal wiki numbering is inspired by [Johnny.Decimal](https://johnnydecimal.com/)
— a simple, sortable system where the tens digit is a category area and the
decimal is an ID within it. The full 00-99 range is available.

---

## Bootstrap (first time only)

If `wiki/` does not exist in this project root, bootstrap it now:

1. Copy the wiki template into place:
   - If `wiki-template/` exists here: `cp -r wiki-template wiki`
   - If this is a fresh project with no template, create the structure manually:
     ```
     wiki/
     ├── README.md                    (copy numbering scheme from wiki-template/README.md)
     ├── 00-09 System & Meta/
     │   ├── 01 Project Conventions/
     │   └── 02 Wiki Index/
     ├── 10-19 Conversations & Decisions/
     │   ├── 11 Key Decisions/
     │   └── 12 Session Logs/
     │       └── 12.01 Session Log Index.md
     ├── 20-29 Implementation & Operations/
     │   ├── 21 Implementation Notes/
     │   └── 22 Workflows/
     ├── 30-39 Integrations & Tooling/
     │   ├── 31 Tool Configs/
     │   └── 32 Integration Notes/
     ├── 40-89 ···  (project-specific categories — add folders as needed)
     └── 90-99 Archive/
         └── 91 Historical Scripts/
     ```
2. Confirm `wiki/README.md` and `wiki/10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md` exist.
3. Ask the user: "What does this project do?" and update the **Scope** section below with a one-line description.
4. Report: "Grimoire wiki bootstrapped at `wiki/`."

If `wiki/` already exists, skip bootstrap and proceed to **Pre-Work Checklist**.

---

## Default Behavior

- Be concise.
- Read before editing.
- Verify important claims with tools.
- Never print secrets.
- Ask before destructive git, machine-level, or security-sensitive changes.
- Do not commit, push, reset, release, or rewrite history unless explicitly asked.

---

## Scope

<!-- Customize this section for your project -->

This project is the canonical home for ...

---

## Grimoire Gate

Agents must maintain the project wiki in `wiki/` using the decimal numbering
system described in `wiki/README.md`.

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

---

## Pre-Work Checklist

Before making any changes:

1. Read `AGENTS.md`, the project `README.md`, and `wiki/README.md`.
2. Scan `wiki/` for notes relevant to the task — especially in the topic's
   folder (Key Decisions, Implementation Notes, Workflows, etc.).
3. Check current state: git branch/status when available, important config
   files, and existing wiki notes.
4. If you are unsure about project conventions or architecture, ask the user
   before editing.

---

## Wiki Update Workflow

After meaningful changes (code, config, workflow, architecture, deployment,
integration, debugging, or policy):

1. **Inspect** `wiki/README.md` for the numbering scheme and scan the relevant
   topic folder for existing notes. The full 00-99 number space is available;
   these categories are predefined:
   - `00-09 System & Meta/01 Project Conventions/`
   - `00-09 System & Meta/02 Wiki Index/`
   - `10-19 Conversations & Decisions/11 Key Decisions/`
   - `10-19 Conversations & Decisions/12 Session Logs/`
   - `20-29 Implementation & Operations/21 Implementation Notes/`
   - `20-29 Implementation & Operations/22 Workflows/`
   - `30-39 Integrations & Tooling/31 Tool Configs/`
   - `30-39 Integrations & Tooling/32 Integration Notes/`
   - `90-99 Archive/91 Historical Scripts/`
   - `40-89` — available for project-specific categories; create a folder
     and start numbering from `.01` when needed.

2. **Update or create** a decimal-numbered note:
   - If a note already covers the topic, **update it in place** (append to it,
     add a dated section).
   - Otherwise, create the **next decimal number** in the most relevant folder
     (e.g. if `21.01.md` and `21.02.md` exist, create `21.03 New Topic.md`).

3. **Keep the note short.** Cover:
   - What changed
   - Why it changed
   - How to verify it
   - Rollback notes (when relevant)

4. **Update the session log index.** Append a line to
   `wiki/10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md`:
   ```
   - YYYY-MM-DD (short description): What happened. [[##.## Note Name]]
   ```

5. **Report** in your final response which wiki file was created or updated.
   If no note was needed, say why (e.g. "read-only inspection — no project
   documentation changed").

---

## Skipping a Wiki Update

Skip for:
- Read-only inspection or Q&A about the project
- Formatting-only edits that don't change behavior
- Trivial typo fixes with no architectural impact

Even when skipping, state that no project documentation changed.
