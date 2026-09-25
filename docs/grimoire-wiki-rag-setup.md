# Grimoire wiki-RAG setup and Hermes boundary

This is the operator record for `johnpippett/grimoire`. It documents the
repository, local checkout, Hermes survey, indexing flow, optional Hermes
registration, 12-hour refresh, verification, and rollback.

## 1. Current state and exact locations

| Item | Value | Meaning |
|---|---|---|
| GitHub repository | [`johnpippett/grimoire`](https://github.com/johnpippett/grimoire) | Owned by `johnpippett`; default branch `main` |
| Upstream commit used | `83eafe4408fdb1d16adfaf8ed6b09a821af91c63` | Current `main` at checkout time |
| Full local project folder | `$PROJECT_DIR` | Complete Git checkout, including `.git`; the host-specific absolute path is kept out of the public repository |
| MCP package | `$PROJECT_DIR/grimoire-mcp` | `uv` project and console entry point |
| Project wiki | `$PROJECT_DIR/wiki` | Bootstrapped from `wiki-template/` |
| Derived index home | `$WIKI_RAG_HOME` or `$HOME/.wiki-rag` | Local, disposable prepared BM25 generations and metadata |
| Hermes home surveyed | `$HERMES_HOME` | Read-only survey target |

The checkout is nested below the task workspace. Its parent can serve as a
test collection root because `grimoire/` is one direct child project. A real
multi-project installation should point `WIKI_RAG_PROJECTS_ROOT` at the
directory whose direct children are the actual projects.

Examples below use `PROJECT_DIR`, `HERMES_HOME`, `HERMES_BIN`, and `UV_BIN` as
operator-local variables. Set them to the corresponding paths on the host;
the public repository intentionally does not record a user's workstation
layout.

To add a project wiki, run `./setup.sh /path/to/project` from this checkout.
Copy `AGENTS.md` into the project root and add a one-sentence scope. The new
`wiki/README.md` is the project entry point. It contains the topic list and the
numbering reference for new notes. See the [wiki template](../wiki-template/README.md).

## 2. What “wiki-RAG” means

`grimoire-mcp` is a local MCP server. It reads Markdown and text files, builds
a derived BM25 index, and returns search results. It does not write or upload
source documentation. Use the [shared local runtime](grimoire-shared-runtime.md)
for Codex and multiple clients. The authenticated HTTP endpoint uses one process.
The stdio mode starts one process per client and is for clients that require it.

The tools are:

- `list_projects`: discovered projects, wiki roots, file counts, and index state.
- `query_wiki`: BM25 search of one registered project's index.
- `read_wiki_passage`: fetch the rest of a search result that has more text.
- `reindex_project`: rebuild one project or all projects with `project="*"`.

MCP search uses registered project indexes. The index can be out of date or can
refer to another checkout. Read the matching file in the active checkout before
you use an indexed result as a current project fact. If MCP search is not
available, use file tools to search and read `wiki/`.

When `query_wiki` marks an excerpt as incomplete, call `read_wiki_passage` with
the result's project, generation, and chunk ID. Use each returned offset until
the tool reports `complete: true`. If its generation is stale, run the search
again and use the new reference. The passage tool does not accept arbitrary file
paths. Do not use an incomplete excerpt as evidence.

Discovery uses `WIKI_RAG_PROJECTS_ROOT`. Every direct child directory is a
project. Sources default to `wiki/`, with optional `Project Vault/`,
`project-vault/`, or `ProjectVault/`. Supported files are `.md`, `.markdown`,
`.mdx`, and `.txt`. Hidden/generated directories such as `.git`, `.venv`,
`node_modules`, `__pycache__`, `.github`, and `.opencode` are skipped.

The derived layout is:

```text
$WIKI_RAG_HOME/
├── indexes/<project-slug>/
│   ├── index.json                 # atomic current-generation pointer/counts
│   └── generations/<id>/          # prepared BM25 files and manifest.json
└── logs/
    ├── server.log
    └── refresh.log
```

Generation files contain indexed source text, path metadata and prepared BM25
data; `index.json` contains counts, roots, generation ID and the indexed timestamp. Treat the derived home as
sensitive as the source projects and rebuild it rather than committing it.

## 3. Hermes survey and strict non-change boundary

The survey inspected these current surfaces without editing them:

- Root config: `$HERMES_HOME/config.yaml`.
- Profile configs: `$HERMES_HOME/profiles/*/config.yaml`.
- Executable: `$HERMES_BIN`.
- Available managed `uv`: `$UV_BIN`.
- `hermes mcp list`: **No MCP servers configured**.
- No `wiki`, `grimoire`, or `WIKI_RAG_PROJECTS_ROOT` entry was present in the
  inspected Hermes root/profile config.

No Hermes service was restarted. No Hermes config, profile, model, gateway,
credential, or MCP registry file was changed. The optional Hermes registration
command in section 7 is documentation only and was not executed.

## 4. Configure the project collection

Create the ignored local config:

```bash
cd "$PROJECT_DIR"
cp config/wiki-rag.env.example config/wiki-rag.env
```

For checkout-only verification, set:

```bash
WIKI_RAG_PROJECTS_ROOT=/path/to/project-collection
WIKI_RAG_HOME=$HOME/.wiki-rag
UV_BIN=/path/to/uv
```

That discovers this checkout as project `grimoire`. For the real collection,
replace the root with the directory that directly contains the project folders.
Earlier sessions observed 18 wiki directories under a `Coding` directory on a
different host; that is historical context, not current evidence on this Linux
checkout. Use it only when it is actually mounted on the host running the
indexer.

Keep `config/wiki-rag.env` uncommitted. It is ignored because private project
paths can disclose workstation layout.

## 5. Install and refresh manually

Install the package environment once:

```bash
"$UV_BIN" sync --directory "$PROJECT_DIR/grimoire-mcp"
```

The package pins the compatible MCP major version as `mcp>=1.0,<2` and the
checked-in `grimoire-mcp/uv.lock` currently resolves `mcp==1.29.0`. The server
source uses the MCP 1.x decorator API (`Server.list_tools` and
`Server.call_tool`); MCP 2.x exposes a different low-level callback API. The
regression test at `grimoire-mcp/tests/test_mcp_compatibility.py` prevents a
future unconstrained upgrade from making the console entry point fail before
it can reindex.

Then run the repository-owned refresh command:

```bash
scripts/refresh-wiki-rag.sh
```

The script reads `config/wiki-rag.env`, creates only the configured derived
directories, exports `WIKI_RAG_PROJECTS_ROOT` and `WIKI_RAG_HOME`, and invokes:

```bash
uv run --directory /absolute/path/to/grimoire/grimoire-mcp grimoire-mcp reindex '*'
```

It does not call Hermes or commit files. Indexing leaves source Markdown intact;
optional automatic adoption adds missing wiki files and agent guidance first. It appends output to `$WIKI_RAG_HOME/logs/refresh.log`.

Record the exact runtime counts from the current run. Do not substitute the
historical 20-index/363-file/915-chunk evidence from the earlier host.

## 6. Verify indexes and queryability

After a refresh:

```bash
INDEX_HOME="${WIKI_RAG_HOME:-$HOME/.wiki-rag}"
find "$INDEX_HOME/indexes" -maxdepth 2 -type f -print | sort
sed -n '1,160p' "$INDEX_HOME/indexes/grimoire/index.json"
tail -n 80 "$INDEX_HOME/logs/refresh.log"
```

The gate is:

1. The expected project appears in refresh output.
2. Its `index.json` reports a positive file count when its wiki has content.
3. The generation referenced by `index.json` exists and queries return results.
4. `git status` shows no source-wiki change caused by indexing.
5. A bounded `query_wiki` request returns a hit from that project.
6. If a result marks its text as incomplete, `read_wiki_passage` returns the
   remaining text through its completion marker.

Use the shared authenticated HTTP endpoint for Codex and multiple clients. See
the [shared local runtime guide](grimoire-shared-runtime.md). Use stdio only for
clients that require it. Do not bind the server to a public listener.

For a standalone stdio client, start the server with:

```bash
"$UV_BIN" run \
  --directory "$PROJECT_DIR/grimoire-mcp" \
  grimoire-mcp
```

### Verified current checkout

The setup was exercised against this checkout after the MCP compatibility pin:

- `uv run --directory grimoire-mcp python -m unittest discover -s tests -v`:
  one test passed.
- `uv run --directory grimoire-mcp grimoire-mcp --version`: `0.1.0`.
- Refresh result: one discovered project (`grimoire`), three files, and three
  chunks.
- Derived metadata: `$WIKI_RAG_HOME/indexes/grimoire/index.json`.
- A bounded query for `Hermes wiki-RAG refresh` returned the wiki note
  `wiki/30-39 Integrations & Tooling/31 Tool Configs/31.01 Grimoire Wiki-RAG and Hermes Boundary.md`.

The counts describe the current checkout only. Adding project folders or wiki
files changes them on the next refresh.

## 7. Optional future Hermes registration (not executed)

If a later task explicitly authorizes changing Hermes, the current CLI accepts
this command shape; `--args` must be the final option:

```bash
"$HERMES_BIN" mcp add grimoire-mcp \
  --command "$UV_BIN" \
  --env WIKI_RAG_PROJECTS_ROOT=/absolute/path/to/project-collection WIKI_RAG_HOME=/absolute/path/to/.wiki-rag \
  --args run --directory /absolute/path/to/grimoire/grimoire-mcp grimoire-mcp
```

This command was not run. If explicitly enabled later, verify with:

```bash
"$HERMES_BIN" mcp list
"$HERMES_BIN" mcp test grimoire-mcp
```

The corresponding future removal command is:

```bash
"$HERMES_BIN" mcp remove grimoire-mcp
```

## 8. Temporary 12-hour refresh

The repository includes a user-level systemd service and timer separate from
Hermes. By default it refreshes only the derived index. With
`WIKI_RAG_AUTO_SETUP=1`, it first creates missing wiki scaffolding and agent
guidance. The
schedule is local midnight and noon:

```text
00:00 local time
12:00 local time
```

`Persistent=true` allows a missed calendar event to run after the user session
returns. Install it for the real collection root with:

```bash
scripts/install-wiki-rag-timer.sh \
  --projects-root /absolute/path/to/project-collection \
  --index-home "$HOME/.wiki-rag"
```

The installer also accepts `--uv-bin`; use the host-specific absolute values
for the checkout and tool on the machine where the timer runs. A portable
example is:

```bash
scripts/install-wiki-rag-timer.sh \
  --projects-root /path/to/project-collection \
  --index-home "$HOME/.wiki-rag" \
  --uv-bin /path/to/uv
```

The named paths must be absolute and must not contain whitespace, quotes,
backslashes, percent specifiers, or newlines because they are rendered into
systemd unit settings. This matches the installer validation.

Only these named units are installed:

```text
$HOME/.config/systemd/user/grimoire-wiki-rag-refresh.service
$HOME/.config/systemd/user/grimoire-wiki-rag-refresh.timer
```

Verify them with:

```bash
systemctl --user status grimoire-wiki-rag-refresh.timer
systemctl --user list-timers grimoire-wiki-rag-refresh.timer
journalctl --user -u grimoire-wiki-rag-refresh.service -n 80 --no-pager
```

The installed user units are expected to show the timer as active and the
service as a valid oneshot. A manual service start is safe when immediate
verification is needed:

```bash
systemctl --user start grimoire-wiki-rag-refresh.service
```

Run an immediate refresh with `scripts/refresh-wiki-rag.sh`. Disable the
temporary schedule while preserving indexes and source documentation:

```bash
scripts/disable-wiki-rag-timer.sh
```

Remove only the installed unit files after disabling:

```bash
scripts/disable-wiki-rag-timer.sh --remove-files
```

This timer is a maintenance convenience, not a documentation author. Humans
and agents still update each project under the required wiki workflow in
`AGENTS.md`.

## 9. Failure diagnosis

### No projects or source files

The root must exist and each project must be a direct child:

```bash
test -d "$WIKI_RAG_PROJECTS_ROOT"
find "$WIKI_RAG_PROJECTS_ROOT" -mindepth 1 -maxdepth 1 -type d -print
```

Check for `wiki/` or a supported vault directory and supported file extensions.

### `uv` cannot be found

Set `UV_BIN` in the ignored local config. The script searches `PATH`,
`$HOME/.local/bin/uv`, and `$HOME/.hermes/bin/uv` when it is unset.

### Stale index

Run the refresh script manually and inspect `refresh.log`. The index is derived
and can be rebuilt safely.

### Timer inactive

Check unit syntax and the user-session bus:

```bash
systemd-analyze verify "$HOME/.config/systemd/user/grimoire-wiki-rag-refresh.service"
systemd-analyze verify "$HOME/.config/systemd/user/grimoire-wiki-rag-refresh.timer"
systemctl --user daemon-reload
systemctl --user enable --now grimoire-wiki-rag-refresh.timer
```

If the user bus is unavailable, the timer is not verified as active; use the
manual refresh command until the session bus is available.

## 10. Security and complete rollback

Source files stay in their repositories. The local prepared index can contain
source text, so protect `$WIKI_RAG_HOME`. Do not publish local config, indexes,
logs, credentials, or private project documentation. The shared HTTP endpoint
binds to `127.0.0.1` and requires a private token. The timer runs without
elevated privileges.

Rollback the indexing setup without touching source wikis or Hermes:

```bash
cd "$PROJECT_DIR"
scripts/disable-wiki-rag-timer.sh --remove-files
rm -rf "$HOME/.wiki-rag"
rm -f config/wiki-rag.env
```

Those cleanup commands target only the exact derived home, local config, and
two named timer units. They preserve the checkout, source wikis, and Hermes.

## 11. Operational contract

An agent that works alone and a coordinator read `wiki/README.md` and the notes
for the task topic before work. A worker may use sufficient wiki context and
source paths from the coordinator. Read more notes only when needed. Search
with ordinary file tools when MCP is unavailable. Use the active checkout for
current facts. Read each incomplete passage through `read_wiki_passage` before
you use it as evidence.

After a topic change or context loss, an agent that works alone and a
coordinator repeat the initial wiki read. A continuing worker uses new,
sufficient wiki context and source paths from the coordinator. Read more notes
only when needed. After meaningful work, agents that work alone and coordinators
update a decimal wiki note and add a short session-log link. Workers return
findings and draft wiki changes unless assigned a specific note. The coordinator
assigns note numbers, updates the session log, and makes final wiki edits. It
can assign a specific note to a worker.

Run a manual reindex when immediate searchability matters; otherwise the
00:00/12:00 timer refreshes the derived index. The timer does not replace the
agent contract.

## 12. Collection rollout and efficient refresh (2026-09-08)

Use `python scripts/setup-projects.py --projects-root /path/to/projects` to preview
adoption, then add `--apply` to create missing wiki files and agent guidance.
Optional `--scopes-json /path/to/scopes.json` supplies directory-name to one-line
scope mappings. Existing wikis and agent instructions are preserved; projects
with redirected managed paths are skipped. Repeat preview should report zero
files. New projects need this adoption step. Set `WIKI_RAG_AUTO_SETUP=1` in the
ignored local environment file to run it before every scheduled/manual refresh.

The local collection now contains five adopted projects. The ignored environment
file points at the actual collection, and the existing timer uses that file.
Refresh reports rebuilt versus unchanged projects. Hashing still reads sources,
but unchanged projects skip chunking, BM25 building, and index writes. See
`grimoire-mcp/README.md` for the persistence/cache protocol and regression commands.

The local Codex registration uses the authenticated shared HTTP endpoint. It
uses one server process and one index cache. The private client configuration
and token are outside this repository. Restart Codex to load a changed
registration. This registration does not configure other harnesses.

## 13. Automatic adoption

The local installation enables `WIKI_RAG_AUTO_SETUP=1`. At midnight and noon the
refresh wrapper first runs `setup-projects.py --apply` against the collection,
then indexes it. New direct-child project directories receive missing wiki
template files, agent guidance, a numbered adoption note and a session-log entry.
Existing content and gates are preserved. Hidden/generated/symlink directories
are skipped. With `--scopes-json`, setup puts the supplied scope in each new
`AGENTS.md` and `wiki/README.md`. Without a supplied scope, it marks the
description as undocumented. It does not guess architecture facts.

Run `scripts/refresh-wiki-rag.sh` for immediate adoption. Set
`GRIMOIRE_WIKI_RAG_DRY_RUN=1` to preview commands without writes. To disable
automatic adoption, change `WIKI_RAG_AUTO_SETUP` to `0` in the local environment
file. Indexing continues and previously created documentation stays in place.

## 14. Preview a contract upgrade

Run the upgrade preview before you apply it:

```bash
python scripts/setup-projects.py --projects-root /path/to/projects --upgrade
python scripts/setup-projects.py --projects-root /path/to/projects --upgrade --apply
```

The preview shows changed lines and does not write files.
The upgrade accepts exact stock Grimoire sections. It skips files with edited
or incomplete sections. It keeps unrelated instructions and the project Scope.
Each changed project gets `AGENTS.md.grimoire-backup` with the original bytes.
Inspect that backup before you use it to restore a contract. Preserve later
edits when you restore a file. The scheduled refresh runs setup without
`--upgrade`, so it does not change existing contracts.
