# Grimoire Wiki-RAG and Scheduled Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure and document `johnpippett/grimoire` as the local cross-project wiki-RAG service, with a reversible 12-hour index refresh and no Hermes configuration changes.

**Architecture:** The repository owns a portable refresh script and systemd unit templates. The script points `grimoire-mcp` at a configurable direct-child project root and writes derived indexes under `WIKI_RAG_HOME`; Hermes remains an optional, explicitly documented consumer rather than an edited dependency.

**Tech Stack:** Bash, systemd user units, `uv`, Python 3.11+, `grimoire-mcp`, Markdown, GitHub repository contents API.

## Global Constraints

- Do not edit `$HERMES_HOME/config.yaml`, any Hermes profile configuration, any Hermes credential file, or the Hermes MCP registry.
- Refresh the index only; never generate, rewrite, delete, or commit source project documentation automatically.
- Keep `WIKI_RAG_PROJECTS_ROOT` and `WIKI_RAG_HOME` configurable; do not commit private paths or secrets.
- Use the existing Grimoire `setup.sh` and upstream CLI entry point rather than forking the indexer.
- Preserve the source wikis and make the derived index disposable and locally stored.

---

### Task 1: Record project scope and create the durable setup documentation

**Files:**
- Modify: `AGENTS.md` (Scope section)
- Modify: `.gitignore` (ignore the local path configuration)
- Create: `config/wiki-rag.env.example`
- Create: `docs/grimoire-wiki-rag-setup.md`
- Create: `wiki/30-39 Integrations & Tooling/31 Tool Configs/31.01 Grimoire Wiki-RAG and Hermes Boundary.md`
- Modify: `wiki/10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md`

**Interfaces:**
- The setup document consumes the repository README, `grimoire-mcp/README.md`,
  the current Hermes survey, and the refresh/timer files from later tasks.
- The example environment file defines `WIKI_RAG_PROJECTS_ROOT`,
  `WIKI_RAG_HOME`, and optional `UV_BIN` for the refresh script.

- [ ] **Step 1: Update the `AGENTS.md` Scope section**

Replace the template sentence with:

```markdown
This project is the canonical home for the Grimoire agent project library,
its per-project wiki contract, and the local grimoire-mcp wiki-RAG service.
```

- [ ] **Step 2: Add the local-config ignore rule and example**

Add `config/wiki-rag.env` to `.gitignore`. Create
`config/wiki-rag.env.example` with comments and these keys, leaving values
empty or explanatory:

```bash
# Copy this file to config/wiki-rag.env and set the absolute root that contains
# one directory per project. Never commit the copied file.
WIKI_RAG_PROJECTS_ROOT=
# Optional; defaults to ~/.wiki-rag.
WIKI_RAG_HOME=
# Optional; defaults to uv on PATH, then the Hermes-managed uv location.
UV_BIN=
```

- [ ] **Step 3: Write the full operator guide**

Document the repository path, current Hermes survey, architecture, source
root rules, installation, local configuration, first reindex, MCP tools,
optional-but-unexecuted Hermes registration, 12-hour timer semantics, health
checks, logs, failure diagnosis, privacy boundary, rollback, uninstall, and
the distinction between reindexing and authoring Markdown. Include the
historical prior-host `Coding` evidence only as clearly labeled prior context
and never as current verification.

- [ ] **Step 4: Add the short wiki decision note and session-log entry**

The note must state what changed, why it changed, verification commands, and
rollback. Add a dated entry to `12.01 Session Log Index.md` pointing to
`31.01 Grimoire Wiki-RAG and Hermes Boundary`.

- [ ] **Step 5: Check documentation for placeholders and contradictions**

Run:

```bash
rg -n 'TBD|TODO|/path/to|CHANGE_ME|REPLACE_ME|\.\.\.' docs config wiki
```

Expected: no `TBD`, `TODO`, or unexplained replacement tokens. Public examples
may use clearly labeled `/path/to/...` values because the exact host paths stay
out of the public repository; the operator replaces those examples locally.

### Task 2: Add the portable refresh command

**Files:**
- Create: `scripts/refresh-wiki-rag.sh`

**Interfaces:**
- Inputs: `WIKI_RAG_PROJECTS_ROOT`, `WIKI_RAG_HOME`, `UV_BIN`, and optional
  `GRIMOIRE_WIKI_RAG_CONFIG`.
- Produces: derived indexes under `WIKI_RAG_HOME/indexes`, a refresh log under
  `WIKI_RAG_HOME/logs/refresh.log`, and the upstream CLI summary on failure or
  interactive execution.

- [ ] **Step 1: Implement configuration resolution and logging**

The script must resolve its own repository directory, source an optional local
config file if it exists, require a non-empty `WIKI_RAG_PROJECTS_ROOT`, create
only `WIKI_RAG_HOME/indexes` and `WIKI_RAG_HOME/logs`, and append a timestamped
run header to `refresh.log`.

- [ ] **Step 2: Resolve `uv` without editing Hermes**

Use `UV_BIN` when supplied, otherwise `command -v uv`, then
`$HOME/.local/bin/uv`, then `$HOME/.hermes/bin/uv`. Fail with an actionable
message if no executable is found.

- [ ] **Step 3: Run the exact upstream reindex operation**

Export `WIKI_RAG_PROJECTS_ROOT` and `WIKI_RAG_HOME`, then run:

```bash
"$UV_BIN" run --directory "$PROJECT_DIR/grimoire-mcp" grimoire-mcp reindex '*'
```

Do not call Hermes, mutate source Markdown, or use a network endpoint.

- [ ] **Step 4: Verify the script**

Run:

```bash
bash -n scripts/refresh-wiki-rag.sh
GRIMOIRE_WIKI_RAG_DRY_RUN=1 WIKI_RAG_PROJECTS_ROOT=/absolute/test/root scripts/refresh-wiki-rag.sh
```

Expected: syntax passes and dry-run prints the resolved project directory,
source root, index home, and command without creating an index.

### Task 3: Add the reversible 12-hour user timer

**Files:**
- Create: `ops/systemd/grimoire-wiki-rag-refresh.service.in`
- Create: `ops/systemd/grimoire-wiki-rag-refresh.timer`
- Create: `scripts/install-wiki-rag-timer.sh`
- Create: `scripts/disable-wiki-rag-timer.sh`

**Interfaces:**
- Installer input: `--projects-root /absolute/path/to/project-root` and the
  optional `--index-home /absolute/path/to/index-home`.
- Installed units: `grimoire-wiki-rag-refresh.service` and
  `grimoire-wiki-rag-refresh.timer` in the user systemd unit directory.
- Timer cadence: local `00:00` and `12:00`, with `Persistent=true`.

- [ ] **Step 1: Write the service template**

Use explicit placeholders for the checkout directory, project root, and index
home. The service must be `Type=oneshot`, call only the repository refresh
script, and contain no Hermes command.

- [ ] **Step 2: Write the timer unit**

Use `OnCalendar=*-*-* 00,12:00:00`, `Persistent=true`, and
`Unit=grimoire-wiki-rag-refresh.service`. Set a descriptive unit name.

- [ ] **Step 3: Implement the installer**

Validate that the requested project root exists and the checkout script exists;
create only `$HOME/.config/systemd/user`, render the service with shell-safe
absolute values, copy the timer template, run `systemctl --user daemon-reload`,
and enable/start the timer. Refuse relative paths and never remove existing
unrelated units.

- [ ] **Step 4: Implement disable/rollback**

Stop and disable the named timer, remove only the two named installed unit files
after an explicit `--remove-files` flag, reload the user daemon, and leave the
source checkout, source wikis, index home, and Hermes untouched.

- [ ] **Step 5: Verify unit syntax and dry-run behavior**

Run `bash -n` on both scripts, render units into a temporary directory, and use
`systemd-analyze verify` when available. If the current user-session bus is not
available, record that exact limitation without claiming the timer is active.

### Task 4: Install dependencies and prove one real index refresh

**Files:**
- Runtime outputs only: the local ignored `config/wiki-rag.env` and
  `$HOME/.wiki-rag/`; no generated index files are committed.

**Interfaces:**
- Uses the committed refresh script and `grimoire-mcp/pyproject.toml`.
- Produces measurable file/chunk counts for the current checkout and an
  explicit statement about whether additional project wikis are mounted.

- [ ] **Step 1: Create a local config for the current checkout**

Set `WIKI_RAG_PROJECTS_ROOT` to the directory containing the cloned `grimoire`
folder, set `WIKI_RAG_HOME` to a user-local derived-data path, and keep this
file ignored.

- [ ] **Step 2: Synchronize the package environment**

Run `uv sync --directory grimoire-mcp` with the resolved `uv` binary and record
the installed package/runtime versions without exposing credentials.

- [ ] **Step 3: Run the refresh script**

Run `scripts/refresh-wiki-rag.sh` and capture the actual `grimoire` file and
chunk counts. Do not report historical cross-project counts as current.

- [ ] **Step 4: Verify derived artifacts and queryability**

Confirm `index.json` and `documents.jsonl` exist under the configured index
home, inspect the metadata, and run one bounded query through the package or
MCP protocol. Confirm the source wiki remains unchanged by comparing its Git
status before and after.

### Task 5: Publish and audit the GitHub project

**Files:**
- Remote target: `johnpippett/grimoire`, default branch `main`.

**Interfaces:**
- Publish only the reviewed repository files from Tasks 1–3 and the required
  wiki note; do not publish local config, derived indexes, logs, credentials,
  or generated environments.

- [ ] **Step 1: Review the local diff**

Run `git diff --check`, inspect `git status --short`, and confirm no ignored
config or index output is staged.

- [ ] **Step 2: Publish the reviewed files through the GitHub connector**

Target exactly `johnpippett/grimoire` on `main`. Use one atomic tree/commit if
the connector returns the current tree SHA; otherwise use sequential contents
writes and verify each resulting commit. Do not modify unrelated files.

- [ ] **Step 3: Synchronize the local checkout**

Fetch the published `main`, verify the local HEAD matches the remote commit, and
confirm the checkout path for the final handoff.

- [ ] **Step 4: Run the completion audit**

Re-read the published setup guide, inspect GitHub file state, re-run local
verification, run `hermes mcp list`, and compare hashes of all Hermes files
surveyed before and after. Report any unavailable user-session or project-root
evidence separately from completed checks.
