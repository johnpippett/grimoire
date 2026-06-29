"""MCP server entry point for wiki-rag-mcp.

Minimal standalone server exposing RAG over project wiki folders (under
~/Coding by default). Core tools: list_projects, query_wiki, reindex_project.

Speaks stdio so it plugs into any MCP harness (OpenCode, Grok, Cursor, etc.).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from . import indexer
from .config import Project, Registry, load_registry

logger = logging.getLogger("wiki_rag")

SERVER_NAME = "wiki-rag-mcp"
SERVER_VERSION = "0.1.0"

# Module-level cache of the registry. Cheap to build (just ``os.walk``), but
# keep it around so successive tool calls don't re-scan the filesystem.
_REGISTRY: Registry | None = None


def _get_registry() -> Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = load_registry()
    return _REGISTRY


def _resolve_project(name: str) -> Project:
    if not name or not name.strip():
        raise ValueError("project name is required")
    project = _get_registry().get(name)
    if project is None:
        names = _get_registry().names()
        raise ValueError(
            f"Unknown project {name!r}. Known projects: {', '.join(names) or '(none)'}"
        )
    return project


def _project_summary(project: Project) -> dict[str, Any]:
    registry = _get_registry()
    files = project.list_source_files() if project.has_any_sources() else []
    meta = indexer.read_meta(project, registry.home)
    return {
        "name": project.name,
        "slug": project.slug,
        "root": str(project.root),
        "wiki_roots": [str(p) for p in project.wiki_roots],
        "wiki_roots_exist": [str(p) for p in project.wiki_roots if p.exists()],
        "source_files": len(files),
        "has_index": indexer.has_index(project, registry.home),
        "indexed_at": meta.get("indexed_at") if meta else None,
        "indexed_files": meta.get("files_indexed") if meta else None,
        "indexed_chunks": meta.get("chunks") if meta else None,
        "bytes_indexed": meta.get("bytes_indexed") if meta else None,
        "description": project.description,
    }


def _format_hit_block(hit: dict[str, Any], index: int) -> str:
    """Format a single BM25 hit as a citation block."""
    header = f"[{index}] {hit['title'] or '(untitled)'}"
    header += f"  — score {hit['score']:.3f}"
    if hit.get("rel_path"):
        header += f"  — {hit['rel_path']}"
    body = hit["text"].strip()
    if len(body) > 1200:
        body = body[:1200].rstrip() + "…"
    return f"{header}\n{body}"


def _query_response(project_name: str, question: str, hits: list[dict[str, Any]]) -> str:
    if not hits:
        return (
            f"No matches in {project_name!r} for: {question!r}\n"
            "Tip: try a different wording, or call `reindex_project` if the "
            "wiki has changed."
        )
    lines = [f"Top {len(hits)} hits in {project_name!r} for: {question!r}", ""]
    for i, hit in enumerate(hits, 1):
        lines.append(_format_hit_block(hit, i))
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# MCP server setup
# ---------------------------------------------------------------------------

app = Server(SERVER_NAME)


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_projects",
            description=(
                "List all Coding projects discovered under the projects root, "
                "with wiki path, source-file count, and whether an index exists."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "include_empty": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include projects that have no wiki sources.",
                    }
                },
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="query_wiki",
            description=(
                "Run a BM25 RAG query against a single project's wiki. Returns "
                "the top-k matching chunks with file path, title, and score. "
                "Use this when you need project-specific documentation context."
            ),
            inputSchema={
                "type": "object",
                "required": ["project", "question"],
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project name to query (matches the folder name under Coding/).",
                    },
                    "question": {
                        "type": "string",
                        "description": "Natural-language question to search for.",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 25,
                        "description": "How many top matching chunks to return.",
                    },
                },
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="reindex_project",
            description=(
                "(Re)build the on-disk index for a Coding project. Run this "
                "when the project's wiki content has changed. Pass project='*' "
                "or omit to reindex all projects that have wiki sources."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "default": "*",
                        "description": "Project name, or '*' / omit for all projects.",
                    }
                },
                "additionalProperties": False,
            },
        ),
    ]


def _tool_result_text(text: str) -> list[types.ContentBlock]:
    return [types.TextContent(type="text", text=text)]


def _tool_result_json(obj: Any) -> list[types.ContentBlock]:
    return [types.TextContent(type="text", text=json.dumps(obj, indent=2))]


@app.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.ContentBlock]:
    args = arguments or {}
    try:
        if name == "list_projects":
            registry = _get_registry()
            include_empty = bool(args.get("include_empty", False))
            out = []
            for project in registry.projects:
                summary = _project_summary(project)
                if not include_empty and summary["source_files"] == 0:
                    continue
                out.append(summary)
            return _tool_result_json(
                {
                    "projects_root": str(registry.projects_root),
                    "home": str(registry.home),
                    "count": len(out),
                    "projects": out,
                }
            )

        if name == "query_wiki":
            project = _resolve_project(str(args.get("project", "")))
            question = str(args.get("question", "")).strip()
            top_k = int(args.get("top_k", 5))
            if not project.has_any_sources():
                return _tool_result_text(
                    f"Project {project.name!r} has no wiki sources on disk."
                )
            if not indexer.has_index(project, _get_registry().home):
                return _tool_result_text(
                    f"Project {project.name!r} has no index yet. Call "
                    "`reindex_project` to build one."
                )
            hits = indexer.query_project(
                project, _get_registry().home, question, top_k=top_k
            )
            return _tool_result_text(
                _query_response(project.name, question, [h.to_dict() for h in hits])
            )

        if name == "reindex_project":
            registry = _get_registry()
            target = str(args.get("project", "*")).strip() or "*"
            if target in {"*", "all"}:
                stats = indexer.index_all(registry)
                return _tool_result_json(
                    {
                        "scope": "all",
                        "indexed": [s.to_dict() for s in stats],
                    }
                )
            project = _resolve_project(target)
            if not project.has_any_sources():
                return _tool_result_text(
                    f"Project {project.name!r} has no wiki sources to index."
                )
            stats = indexer.index_project(project, registry.home)
            return _tool_result_json(
                {"scope": project.name, "indexed": [stats.to_dict()]}
            )

        return _tool_result_text(f"Unknown tool: {name}")
    except (ValueError, FileNotFoundError) as exc:
        return _tool_result_text(f"Error: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool %s failed", name)
        return _tool_result_text(f"Error ({type(exc).__name__}): {exc}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def _configure_logging() -> None:
    default_log = str(
        Path(
            os.environ.get(
                "WIKI_RAG_HOME", str(Path.home() / ".wiki-rag")
            )
        )
        / "logs"
        / "server.log"
    )
    log_path = Path(os.environ.get("WIKI_RAG_LOG", default_log))
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
    except Exception:  # noqa: BLE001
        logging.basicConfig(level=logging.INFO)
    # Quiet llama-index a bit.
    logging.getLogger("llama_index").setLevel(logging.WARNING)


async def _run() -> None:
    _configure_logging()
    logger.info("starting %s v%s", SERVER_NAME, SERVER_VERSION)
    # Eagerly build the registry so the first tool call is fast.
    registry = _get_registry()
    logger.info(
        "discovered %d projects under %s",
        len(registry.projects),
        registry.projects_root,
    )
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main() -> None:
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] in {"--help", "-h", "help"}:
        print("wiki-rag-mcp: MCP server for per-project wiki RAG.")
        print("Usage: wiki-rag-mcp   (runs as stdio MCP server)")
        print("       wiki-rag-mcp reindex [project|*]   (reindex without MCP)")
        print("Env: WIKI_RAG_HOME, WIKI_RAG_PROJECTS_ROOT, WIKI_RAG_LOG")
        print("See README.md for OpenCode config and tool list.")
        _sys.exit(0)
    if len(_sys.argv) > 1 and _sys.argv[1] in {"--version", "-v"}:
        print(f"wiki-rag-mcp {SERVER_VERSION}")
        _sys.exit(0)
    if len(_sys.argv) > 1 and _sys.argv[1] == "reindex":
        # Standalone reindex CLI (no MCP needed)
        import os as _os
        from .config import load_registry
        from . import indexer as _indexer
        target = _sys.argv[2] if len(_sys.argv) > 2 else "*"
        _os.environ.setdefault("WIKI_RAG_HOME", str(_os.path.expanduser("~/.wiki-rag")))
        reg = load_registry()
        if target in {"*", "all"}:
            stats = _indexer.index_all(reg)
            print(f"Reindexed {len(stats)} projects.")
            for s in stats:
                print(f"  {s.project}: {s.files_indexed} files, {s.chunks} chunks")
        else:
            proj = reg.get(target)
            if not proj:
                print(f"Unknown project: {target}. Known: {', '.join(reg.names()[:5])}...")
                _sys.exit(1)
            if not proj.has_any_sources():
                print(f"No sources for {target}")
                _sys.exit(1)
            s = _indexer.index_project(proj, reg.home)
            print(f"Reindexed {s.project}: {s.files_indexed} files, {s.chunks} chunks in {s.duration_s:.2f}s")
        _sys.exit(0)
    try:
        import asyncio

        asyncio.run(_run())
    except KeyboardInterrupt:
        _sys.exit(0)


if __name__ == "__main__":
    main()
