# Grimoire Wiki-RAG and 12-Hour Refresh Design

## Goal

Make `johnpippett/grimoire` the durable, documented source for cross-project
wiki retrieval, and provide a reversible host-side refresh every 12 hours
without changing any Hermes configuration element.

## Current evidence

- The target repository is `johnpippett/grimoire`, owned by the authenticated
  GitHub user `johnpippett`.
- The repository's `grimoire-mcp` package exposes `list_projects`,
  `query_wiki`, and `reindex_project`; it discovers direct child projects under
  `WIKI_RAG_PROJECTS_ROOT` and persists local indexes under `WIKI_RAG_HOME`.
- The current Hermes installation is represented by `$HERMES_HOME`.
- `$HERMES_HOME/config.yaml` contains no Grimoire or wiki-RAG entry,
  and `hermes mcp list` reports no configured MCP servers.
- The current sandbox does not contain the historical prior-host `Coding`
  project tree or any mounted project `wiki/` directories. Earlier-session
  evidence of 18 wiki directories, 20 indexes, 363 files, and 915 chunks is
  retained as historical context, not current-state proof.

## Design

1. Keep the repository self-contained. Bootstrap its own `wiki/`, document the
   integration in `docs/`, and keep a short decimal-numbered decision note in
   the repository wiki.
2. Use a repository-owned refresh script. It resolves `uv` without assuming
   that Hermes has been modified, accepts a configurable project root, writes
   only to `WIKI_RAG_HOME`, and runs the upstream CLI command
   `grimoire-mcp reindex "*"`.
3. Install a user-level systemd service and timer outside Hermes. The timer
   runs at local midnight and noon, catches up after downtime through
   `Persistent=true`, and can be disabled or removed independently.
4. Do not run `hermes mcp add`, edit `.hermes/config.yaml`, edit profile
   configuration, restart Hermes, or change any Hermes credential file. The
   documentation will include the exact optional Hermes command for a future
   explicit opt-in, but it will remain unexecuted.
5. Treat “update docs” as “refresh the index over existing Markdown”. Grimoire
   does not author or rewrite source documentation; agents and humans update
   the project wikis, and the timer makes those changes searchable.

## Data flow

```text
project-root/*/wiki/ or Project Vault/
             |
             v
refresh-wiki-rag.sh
             |
             v
grimoire-mcp reindex "*"
             |
             v
WIKI_RAG_HOME/indexes/<project-slug>/
             |
             v
Hermes (optional future MCP registration) -> list/query/reindex tools
```

The source Markdown remains in each project. The index is local, derived, and
re-creatable. No network service or embedding model is introduced.

## Acceptance criteria

- The checkout path is recorded exactly.
- The repository has a complete setup and rollback document.
- `AGENTS.md` has a real Grimoire scope instead of the template placeholder.
- A local config example does not contain secrets or machine-specific values.
- The refresh script passes shell syntax checks and performs a real bounded
  reindex against the current checkout.
- The timer files and install/disable instructions are present and tested as
  far as the current user-session bus permits.
- Hermes configuration files and the Hermes MCP registry are byte-for-byte
  unchanged by this work.

## Rollback

Disable the timer, remove the two installed user units, and delete only the
derived `WIKI_RAG_HOME` directory if its contents are no longer wanted. The
source wikis, Grimoire checkout, and all Hermes files are preserved.
