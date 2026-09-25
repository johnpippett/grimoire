# grimoire-mcp

Local MCP server for search across project wiki folders.

The server reads Markdown and text files. It builds a BM25 index and returns
search results. It does not write source wiki files.

## Features

- One persistent BM25 index per project (zero embedding models, deterministic, fast, no GPU).
- MCP tools: `list_projects`, `query_wiki`, `read_wiki_passage`, and
  `reindex_project`.
- Re-index easily when docs change.
- Configurable via `~/.wiki-rag/projects.json` (include/exclude/overrides).
- A shared local HTTP endpoint, plus a standalone stdio mode.
- Auto-discovers wikis under your projects root (set via `WIKI_RAG_PROJECTS_ROOT`).

## Project Structure

- `src/wiki_rag/` - the package
  - `config.py` - project discovery + registry
  - `indexer.py` - document walking, chunking, BM25 persistence + query
  - `server.py` - MCP server exposing the tools
- `~/.wiki-rag/indexes/` - persisted documents + meta
- `~/.wiki-rag/logs/` - server logs

## Install and index

```bash
cd grimoire-mcp

# Install the locked package environment
uv sync
```

Set `WIKI_RAG_PROJECTS_ROOT` to the directory that contains your project
directories. The default is `~/projects`. Build the indexes with:

```bash
uv run grimoire-mcp reindex "*"
```

The server writes logs to `~/.wiki-rag/logs/server.log`.

## Configuration

Set the projects root via environment variable:

```bash
export WIKI_RAG_PROJECTS_ROOT=~/my-projects
```

Default is `~/projects`. All subdirectories are treated as projects — each one
with a `wiki/` folder will be discovered automatically.

Optional `~/.wiki-rag/projects.json` to include/exclude projects or override wiki roots:

```json
{
  "include": ["My App", "My Lib"],
  "exclude": ["Archived Project"],
  "overrides": {
    "My App": {
      "wiki_roots": ["/path/to/custom/docs"],
      "description": "The main application"
    }
  }
}
```

## Shared HTTP connections

Use [the shared local runtime](../docs/grimoire-shared-runtime.md) for Codex and
for multiple agents. It binds to `127.0.0.1`, requires a private bearer token,
and serves one process and cache. The default endpoint is
`http://127.0.0.1:8767/mcp`.

## Stdio for clients that require it

Each stdio client starts a separate server process. This mode does not share a
process across agents. Use it only when a client requires stdio.

Add to your MCP client config:

```json
{
  "mcpServers": {
    "grimoire-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/grimoire-mcp", "grimoire-mcp"]
    }
  }
}
```

Use this configuration only with an MCP client that requires stdio.

Restart the client after adding.

## Core Tools

- `list_projects` — list registered projects and index state.
- `query_wiki` — search one project's indexed wiki with `project` and `question`.
  It returns source paths, index generation, and bounded excerpts.
- `read_wiki_passage` — read a complete indexed chunk in bounded parts. Pass
  the `project`, `generation`, and `chunk_id` from a search result. Pass the
  returned `next_offset` to read the next part. Continue until `complete` is
  true before relying on an excerpt marked as incomplete. This tool does not
  read arbitrary file paths. If the generation is stale, run the search again.
- `reindex_project` — update one project's index. Use `"*"` to update all
  registered projects.

`query_wiki` searches registered project indexes. An index can be out of date
or can refer to another checkout. Read the matching file in the active checkout
before using an indexed result as a current project fact. If MCP search is not
available, use file tools to search the wiki, for example `rg --files wiki` and
`rg -n "term" wiki`.

## Quick Reindex (CLI, no MCP needed)

```bash
uv run --directory /path/to/grimoire-mcp grimoire-mcp reindex "*"
```

## Security

Only scans under the configured projects root. Never walks outside that tree.

## Implementation

- LlamaIndex `SentenceSplitter` + `BM25Retriever` (no embeddings/GPU).
- Per-project JSONL + meta persisted under `~/.wiki-rag/indexes/`.
- Skips generated dirs (`.git`, `node_modules`, etc.).

## Efficient refresh and query behavior

Refresh hashes source bytes and indexing settings. Unchanged projects retain
their published generation and report `unchanged: true`. Changed projects build
prepared BM25 data once and publish it by atomically replacing `index.json`.
The manifest and BM25 JSON/NumPy files live under `generations/<id>/`; obsolete
generations are removed after publication. Legacy raw-document indexes migrate
from current source files on their first query or refresh.

Queries reuse an LRU cache of up to eight projects with a 64 MiB persisted-data
admission budget (this is not an exact Python heap limit). Generation changes
invalidate cached data across server processes. POSIX file locks coordinate
writers and cold readers; this implementation targets Linux/macOS.

MCP tool work runs in four bounded workers so filesystem and indexing work does
not block the event loop. `list_projects` defaults to timestamped indexed counts;
`source_files` is null when unknown. Pass `live_scan: true` for current recursive
counts, including empty or unreadable source files. Listing and reindexing refresh
project discovery so newly added projects appear without restarting the server.

## Tests and benchmark

```bash
uv run --with pytest python -m pytest tests ../tests -q
uv run python benchmarks/benchmark_indexer.py
```

The benchmark uses disposable synthetic documents and reports initial build,
unchanged refresh, cold/warm queries and process peak RSS. Compare measurements
under the same Python and locked dependencies. Source hashing still reads all
files during refresh; unchanged projects avoid chunking, BM25 construction and
index rewriting.

Sentence boundaries use a simple punctuation/whitespace heuristic, with paragraph
and token-budget splitting handled by SentenceSplitter. Indexing long notes does
not import NLTK or download its tokenizer data. Boundary-setting changes invalidate
the source manifest and rebuild prepared data on the next refresh.
