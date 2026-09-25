<p align="center">
  <img src="https://github.com/johnpippett/grimoire/blob/main/logo.jpg?raw=true" alt="Grimoire" width="60%" />
</p>

<h1 align="center">Grimoire — Agent Project Library</h1>

Grimoire stores project knowledge in Markdown files beside the code. The
`AGENTS.md` contract tells agents when to read and update the wiki. The optional
`grimoire-mcp` service searches indexed wikis across projects.

## The three parts

### Project wiki

Each project has a `wiki/` directory. Its `README.md` is the entry point. It
holds a short project summary, terms, current work, constraints, and links to
useful topic notes. An agent that works alone reads it and the notes for the
task topic before work. A coordinator does the same before it assigns work.
The numbering reference explains how to name new notes.

Topic notes record decisions and meaningful changes. Each note states what
changed, why, how to verify it, and how to roll it back when needed.

### Agent contract

Copy `AGENTS.md` into the project root. It gives a portable contract for wiki
orientation, search, documentation, and final reports. It also covers public
technical writing. Setup steps and the note numbering reference live in this
README and in the wiki template.

Use the same contract in every harness. If a harness reads a different project
instruction file, copy the contract into that file. Do not remove the required
wiki steps.

### Cross-project search

`grimoire-mcp` provides local search with BM25. It does not write source wiki
files. Its tools are:

- `list_projects` — show registered projects and index state.
- `query_wiki` — search one project's indexed wiki.
- `read_wiki_passage` — read a full indexed passage in bounded parts.
- `reindex_project` — update one or all project indexes.

Search covers registered project indexes. It can be stale or refer to another
checkout. Read the matching file in the active checkout before using a result
as a current project fact. When a result marks a passage as incomplete, read
each part with `read_wiki_passage`, using its project, generation, and chunk ID,
until the passage is complete. See the [MCP guide](grimoire-mcp/README.md).

## Quick start

### 1. Add the wiki

Run the setup script from the Grimoire repository:

```bash
./setup.sh /path/to/your-project
```

Or copy the template into your project:

```bash
cp -r /path/to/grimoire/wiki-template /path/to/your-project/wiki
```

Add a one-sentence project summary, terms, current work, constraints, and links
to useful notes in `wiki/README.md`.

### 2. Add the agent contract

Copy the contract to the project root:

```bash
cp /path/to/grimoire/AGENTS.md /path/to/your-project/AGENTS.md
```

Replace the **Scope** section with one sentence about the project. If your
harness uses another instruction filename, copy the same contract into that
file. The contract must keep the wiki orientation and update steps.

### 3. Set up optional search

Install the local MCP package:

```bash
cd grimoire-mcp
uv sync
```

Set `WIKI_RAG_PROJECTS_ROOT` to the directory that contains your project
directories. See the [shared local runtime guide](docs/grimoire-shared-runtime.md)
to connect multiple clients to one authenticated HTTP service. Use that HTTP
connection for Codex. Each stdio client starts its own process; use stdio only
when a client requires it. See the [MCP guide](grimoire-mcp/README.md) for
other connection options.

### 4. Start project work

An agent that works alone reads `wiki/README.md` and the notes for the task
topic before work. A coordinator does the same before it assigns work.
Search the wiki before asking the user to repeat a decision or explain a term.
Use file tools if MCP search is unavailable.

A worker may use sufficient wiki context and source paths from the coordinator.
It reads more notes only when needed. After a topic change or context loss, an
agent that works alone repeats this initial wiki read. A coordinator does the
same. A continuing worker uses new, sufficient wiki context and source paths
from the coordinator. It reads more notes only when needed.

After meaningful work, agents that work alone and coordinators update a topic
note. They add one short link to the session log. A worker returns findings and
draft wiki changes. It edits a wiki note only when the coordinator assigns it.
The coordinator assigns note numbers, updates the session log, and makes final
wiki edits. It can assign a specific note to a worker.
If no project knowledge changed, state why no wiki note was needed.

## Set up a project collection

The setup script previews changes by default. Add `--apply` to write them:

```bash
python scripts/setup-projects.py --projects-root /path/to/projects
python scripts/setup-projects.py --projects-root /path/to/projects --apply
```

The script adds missing wiki files and agent guidance. It keeps existing files.
Use `--scopes-json` with a JSON object to set one-line descriptions for new
contracts. Repeated runs do not add duplicate files. Set
`WIKI_RAG_PROJECTS_ROOT` to the same directory, then refresh the indexes.

To adopt new projects during scheduled refreshes, set `WIKI_RAG_AUTO_SETUP=1` in
the ignored `config/wiki-rag.env` file. The refresh runs setup before indexing.
Set the value to `0` to disable adoption. The refresh continues to update
indexes.

For full install, verification, and rollback steps, see the
[wiki-RAG setup guide](docs/grimoire-wiki-rag-setup.md).

### Upgrade an existing contract

Preview recognized Grimoire instructions before you change them:

```bash
python scripts/setup-projects.py --projects-root /path/to/projects --upgrade
python scripts/setup-projects.py --projects-root /path/to/projects --upgrade --apply
```

The preview shows changed lines and does not write files.
The upgrade accepts exact stock Grimoire sections and skips edited or unclear
files. It keeps unrelated instructions and saves the original `AGENTS.md` bytes
as `AGENTS.md.grimoire-backup` in each changed project. Inspect the preview
before you apply it. Scheduled index refreshes do not run contract upgrades.

## Files

| File | Purpose |
|---|---|
| `AGENTS.md` | Portable wiki contract for project agents |
| `setup.sh` | Copy the wiki template into one project |
| `scripts/setup-projects.py` | Preview or apply wiki setup across projects |
| `wiki-template/` | Starter wiki and numbering reference |
| `grimoire-mcp/` | Local server for cross-project wiki search |
| `skills/` | Optional workflow guides for agents that support skills |

## License

MIT.
