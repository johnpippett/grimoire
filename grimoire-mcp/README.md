# grimoire-mcp

**One standalone MCP server for RAG over your project wiki folders.**

Plug it into any agent harness (Claude, Cursor, OpenCode, Grok, etc.). Agents get simple tools to discover projects and query the wiki/docs for the project they're working in.

Uses LlamaIndex + BM25 (no embeddings, fast, deterministic, local-only).

## Features

- One persistent BM25 index per project (zero embedding models, deterministic, fast, no GPU).
- Minimal tools: `list_projects`, `query_wiki`, `reindex_project`.
- Re-index easily when docs change.
- Configurable via `~/.wiki-rag/projects.json` (include/exclude/overrides).
- Fully standalone stdio MCP — plug into any harness.
- Auto-discovers wikis under your projects root (set via `WIKI_RAG_PROJECTS_ROOT`).

## Project Structure

- `src/wiki_rag/` - the package
  - `config.py` - project discovery + registry
  - `indexer.py` - document walking, chunking, BM25 persistence + query
  - `server.py` - MCP server exposing the tools
- `~/.wiki-rag/indexes/` - persisted documents + meta
- `~/.wiki-rag/logs/` - server logs

## Quick Start

```bash
cd grimoire-mcp

# Install / run with uv (recommended)
uv sync
uv run grimoire-mcp

# Or pip
python -m venv .venv
. .venv/bin/activate
pip install -e .
grimoire-mcp
```

The server speaks stdio MCP. It will log to `~/.wiki-rag/logs/server.log`.

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

## Plug and Play

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

Works with Claude Desktop, Cursor, OpenCode, Grok, and any other stdio MCP client.

Restart the client after adding.

## Core Tools

- `list_projects` — discover available projects + wiki status.
- `query_wiki` — RAG search a specific project's wiki (pass `project` name + `question`).
- `reindex_project` — rebuild index after wiki changes (supports `"*"` for all).

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
