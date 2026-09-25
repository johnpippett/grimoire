"""MCP server entry point for grimoire-mcp.

Minimal standalone server exposing RAG over project wiki folders.
Core tools: list_projects, query_wiki, read_wiki_passage, reindex_project.

Supports stdio clients and an authenticated shared HTTP endpoint.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from weakref import WeakKeyDictionary

import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from . import indexer
from .config import Project, Registry, load_registry

logger = logging.getLogger("wiki_rag")

SERVER_NAME = "grimoire-mcp"
SERVER_VERSION = "0.1.0"
_RESPONSE_MAX_CHARS = 8000
_QUERY_EXCERPT_CHARS = 1200
_PASSAGE_PAGE_CHARS = 3500

# Queries reuse discovery; listing and refresh requests reload it explicitly.
_REGISTRY: Registry | None = None


def _get_registry(*, refresh: bool = False) -> Registry:
    global _REGISTRY
    if refresh or _REGISTRY is None:
        _REGISTRY = load_registry()
    return _REGISTRY


def _resolve_project(name: str, registry: Registry | None = None) -> Project:
    if not name or not name.strip():
        raise ValueError("project name is required")
    registry = registry or _get_registry()
    project = registry.get(name)
    if project is None:
        names = registry.names()
        raise ValueError(
            f"Unknown project {name!r}. Known projects: {', '.join(names) or '(none)'}"
        )
    return project


def _project_summary(
    project: Project, registry: Registry | None = None, *, live_scan: bool = False
) -> dict[str, Any]:
    registry = registry or _get_registry()
    meta = indexer.read_meta(project, registry.home)
    if live_scan:
        count = len(project.list_source_files())
        basis = "live"
        counted_at = datetime.now(timezone.utc).isoformat()
    else:
        count = meta.get("source_file_count", meta.get("files_indexed")) if meta else None
        basis = "indexed" if count is not None else "unknown"
        counted_at = meta.get("indexed_at") if meta else None
    return {
        "name": project.name,
        "slug": project.slug,
        "root": str(project.root),
        "wiki_roots": [str(p) for p in project.wiki_roots],
        "wiki_roots_exist": [str(p) for p in project.wiki_roots if p.exists()],
        "source_files": count,
        "source_files_basis": basis,
        "source_files_at": counted_at,
        "has_index": indexer.has_index(project, registry.home),
        "indexed_at": meta.get("indexed_at") if meta else None,
        "indexed_files": meta.get("files_indexed") if meta else None,
        "indexed_chunks": meta.get("chunks") if meta else None,
        "bytes_indexed": meta.get("bytes_indexed") if meta else None,
        "description": project.description,
    }


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _shorten(value: Any, limit: int) -> tuple[str, bool]:
    """Limit the JSON form of a string, including escaped control characters."""
    text = str(value)
    if len(text) <= limit and len(_json_text(text)) <= limit:
        return text, False
    low, high = 0, min(len(text), limit)
    shortened = "…"
    while low <= high:
        middle = (low + high) // 2
        candidate = text[:middle] + "…"
        if len(_json_text(candidate)) <= limit:
            shortened = candidate
            low = middle + 1
        else:
            high = middle - 1
    return shortened, True


def _shorten_roots(values: Any) -> tuple[list[str], bool]:
    roots = values if isinstance(values, list) else []
    shortened: list[str] = []
    changed = len(roots) > 8
    for value in roots[:8]:
        root, truncated = _shorten(value, 256)
        shortened.append(root)
        changed = changed or truncated
    return shortened, changed


def _query_response(
    project_name: str,
    question: str,
    hits: list[dict[str, Any]],
    meta: dict[str, Any] | None,
) -> str:
    """Return source references and excerpts within the MCP response limit."""
    first = hits[0] if hits else {}
    question_text, question_truncated = _shorten(question, 500)
    roots, roots_truncated = _shorten_roots(first.get("wiki_roots", (meta or {}).get("wiki_roots", [])))
    project_text, project_truncated = _shorten(project_name, 255)
    payload: dict[str, Any] = {
        "project": project_text,
        "question": question_text,
        "question_truncated": question_truncated,
        "generation": first.get("generation", (meta or {}).get("generation")),
        "indexed_at": first.get("indexed_at", (meta or {}).get("indexed_at")),
        "wiki_roots": roots,
        "provenance_truncated": project_truncated or roots_truncated,
        "results": [],
        "returned_hits": 0,
        "omitted_hits": len(hits),
    }
    if not hits:
        payload["message"] = "No positive-score matches. Try a different query or reindex the project wiki."
        rendered = _json_text(payload)
        if len(rendered) <= _RESPONSE_MAX_CHARS:
            return rendered
        return _json_text({
            "project": project_text,
            "generation": payload["generation"],
            "indexed_at": payload["indexed_at"],
            "wiki_roots": roots[:2],
            "results": [],
            "returned_hits": 0,
            "omitted_hits": 0,
            "response_truncated": True,
            "message": "No positive-score matches.",
        })

    results: list[dict[str, Any]] = []

    def make_result(hit: dict[str, Any], excerpt_chars: int) -> dict[str, Any]:
        text = hit["text"][:excerpt_chars]
        truncated = excerpt_chars < len(hit["text"])
        file_path, file_truncated = _shorten(hit.get("file_path", ""), 512)
        rel_path, rel_truncated = _shorten(hit.get("rel_path", ""), 512)
        title, title_truncated = _shorten(hit.get("title", ""), 120)
        hit_project, project_truncated = _shorten(hit.get("project", project_name), 255)
        hit_roots, roots_truncated = _shorten_roots(hit.get("wiki_roots", []))
        return {
            "score": hit["score"],
            "text": text,
            "file_path": file_path,
            "rel_path": rel_path,
            "title": title,
            "project": hit_project,
            "wiki_roots": hit_roots,
            "indexed_at": hit["indexed_at"],
            "generation": hit["generation"],
            "chunk_id": hit["chunk_id"],
            "passage_length": len(hit["text"]),
            "excerpt_truncated": truncated,
            "next_offset": excerpt_chars if truncated else None,
            "provenance_truncated": file_truncated or rel_truncated or title_truncated or project_truncated or roots_truncated,
        }

    for hit in hits:
        full_length = len(hit["text"])
        excerpt_length = min(_QUERY_EXCERPT_CHARS, full_length)
        candidate = make_result(hit, excerpt_length)

        def render(candidate_results: list[dict[str, Any]]) -> str:
            omitted = len(hits) - len(candidate_results)
            payload["results"] = candidate_results
            payload["returned_hits"] = len(candidate_results)
            payload["omitted_hits"] = omitted
            payload["response_truncated"] = omitted > 0 or question_truncated or payload["provenance_truncated"] or any(
                result["excerpt_truncated"] or result["provenance_truncated"]
                for result in candidate_results
            )
            return _json_text(payload)

        if len(render([*results, candidate])) <= _RESPONSE_MAX_CHARS:
            results.append(candidate)
            continue

        low, high = 0, excerpt_length
        best: dict[str, Any] | None = None
        while low <= high:
            middle = (low + high) // 2
            smaller = make_result(hit, middle)
            if len(render([*results, smaller])) <= _RESPONSE_MAX_CHARS:
                best = smaller
                low = middle + 1
            else:
                high = middle - 1
        if best is None or not best["text"]:
            continue
        results.append(best)

    rendered = render(results)
    if len(rendered) > _RESPONSE_MAX_CHARS:
        payload = {
            "project": project_text,
            "generation": payload["generation"],
            "indexed_at": payload["indexed_at"],
            "wiki_roots": roots[:2],
            "results": [],
            "returned_hits": 0,
            "omitted_hits": len(hits),
            "response_truncated": True,
            "provenance_truncated": True,
        }
        rendered = _json_text(payload)
    return rendered


def _passage_response(passage: dict[str, Any], offset: int) -> str:
    text = passage["text"]
    if offset > len(text):
        raise ValueError("offset must be within the indexed passage")
    available = min(_PASSAGE_PAGE_CHARS, len(text) - offset)
    project, project_truncated = _shorten(passage.get("project", ""), 255)
    file_path, file_truncated = _shorten(passage.get("file_path", ""), 512)
    rel_path, rel_truncated = _shorten(passage.get("rel_path", ""), 512)
    title, title_truncated = _shorten(passage.get("title", ""), 120)
    roots, roots_truncated = _shorten_roots(passage.get("wiki_roots", []))

    def make_page(length: int) -> dict[str, Any]:
        next_offset = offset + length
        return {
            "project": project,
            "file_path": file_path,
            "rel_path": rel_path,
            "title": title,
            "wiki_roots": roots,
            "indexed_at": passage["indexed_at"],
            "generation": passage["generation"],
            "chunk_id": passage["chunk_id"],
            "offset": offset,
            "text": text[offset:next_offset],
            "next_offset": next_offset,
            "passage_length": len(text),
            "complete": next_offset >= len(text),
            "provenance_truncated": project_truncated or file_truncated or rel_truncated or title_truncated or roots_truncated,
        }

    low, high = 0, available
    best = make_page(0)
    while low <= high:
        middle = (low + high) // 2
        page = make_page(middle)
        if len(_json_text(page)) <= _RESPONSE_MAX_CHARS:
            best = page
            low = middle + 1
        else:
            high = middle - 1
    return _json_text(best)


# ---------------------------------------------------------------------------
# MCP server setup
# ---------------------------------------------------------------------------

_WORKER_COUNT = 4
_WORKERS = ThreadPoolExecutor(max_workers=_WORKER_COUNT, thread_name_prefix="wiki-rag")
_WORKER_SLOTS: WeakKeyDictionary = WeakKeyDictionary()

app = Server(SERVER_NAME)


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_projects",
            description=(
                "List all Coding projects discovered under the projects root, "
                "with wiki path, indexed source-file count and timestamp, and index status. "
                "Unindexed counts are unknown; set live_scan for current file counts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "include_empty": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include projects with no wiki roots or zero known sources.",
                    },
                    "live_scan": {
                        "type": "boolean",
                        "default": False,
                        "description": "Recursively count current sources instead of using indexed metadata.",
                    }
                },
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="query_wiki",
            description=(
                "Search the registered index for one project's wiki. Results include "
                "positive BM25 scores, source paths, indexed roots, index time, "
                "generation, chunk IDs, and short excerpts. Read an incomplete "
                "excerpt with read_wiki_passage before use. Read the active checkout "
                "for checkout-specific facts."
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
            name="read_wiki_passage",
            description=(
                "Read one indexed passage by project, generation, and chunk ID. "
                "Use offset for character pagination. Read each page until complete "
                "is true. If the generation is stale, run query_wiki again. "
                "Do not use a file path."
            ),
            inputSchema={
                "type": "object",
                "required": ["project", "generation", "chunk_id"],
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Registered project name.",
                    },
                    "generation": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{32}$",
                        "description": "Generation ID returned by query_wiki.",
                    },
                    "chunk_id": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                        "description": "Chunk ID returned by query_wiki.",
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Character offset in the indexed chunk.",
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
    loop = asyncio.get_running_loop()
    slots = _WORKER_SLOTS.setdefault(loop, asyncio.Semaphore(_WORKER_COUNT))
    await slots.acquire()
    try:
        future = _WORKERS.submit(_call_tool_sync, name, arguments)
    except BaseException:
        slots.release()
        raise

    def release_slot(_future):
        # Cancellation of a request cannot free a slot while its thread runs.
        try:
            loop.call_soon_threadsafe(slots.release)
        except RuntimeError:
            pass  # The owning event loop has already shut down.

    future.add_done_callback(release_slot)
    return await asyncio.wrap_future(future)


def _call_tool_sync(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
    args = arguments or {}
    try:
        if name == "list_projects":
            registry = _get_registry(refresh=True)
            live_scan = bool(args.get("live_scan", False))
            include_empty = bool(args.get("include_empty", False))
            out = []
            for project in registry.projects:
                summary = _project_summary(project, registry, live_scan=live_scan)
                if not include_empty and (
                    not project.has_any_sources() or summary["source_files"] == 0
                ):
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
            registry = _get_registry()
            project_name = args.get("project", "")
            if not isinstance(project_name, str):
                raise ValueError("project must be a registered project name")
            project = _resolve_project(project_name, registry)
            question = args.get("question", "")
            if not isinstance(question, str) or not question.strip():
                raise ValueError("question must be a non-empty string")
            top_k = args.get("top_k", 5)
            if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 25:
                raise ValueError("top_k must be an integer between 1 and 25")
            if not project.has_any_sources():
                return _tool_result_text(
                    f"Project {project.name!r} has no wiki sources on disk."
                )
            if not indexer.has_index(project, registry.home):
                return _tool_result_text(
                    f"Project {project.name!r} has no index yet. Call "
                    "`reindex_project` to build one."
                )
            query_hits = indexer.query_project(
                project, registry.home, question, top_k=top_k
            )
            return _tool_result_text(
                _query_response(
                    project.name, question, [h.to_dict() for h in query_hits],
                    query_hits.index_meta(),
                )
            )

        if name == "read_wiki_passage":
            registry = _get_registry()
            project_name = args.get("project", "")
            if not isinstance(project_name, str):
                raise ValueError("project must be a registered project name")
            project = _resolve_project(project_name, registry)
            generation = args.get("generation", "")
            chunk_id = args.get("chunk_id", "")
            offset = args.get("offset", 0)
            if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
                raise ValueError("offset must be a non-negative integer")
            passage = indexer.read_passage(
                project, registry.home, generation, chunk_id
            )
            return _tool_result_text(_passage_response(passage, offset))

        if name == "reindex_project":
            registry = _get_registry(refresh=True)
            target = str(args.get("project", "*")).strip() or "*"
            if target in {"*", "all"}:
                stats = indexer.index_all(registry)
                return _tool_result_json(
                    {
                        "scope": "all",
                        "indexed": [s.to_dict() for s in stats],
                    }
                )
            project = _resolve_project(target, registry)
            if not project.has_any_sources() and not indexer.has_index(project, registry.home):
                return _tool_result_text(
                    f"Project {project.name!r} has no wiki sources to index."
                )
            stats = indexer.index_project(project, registry.home)
            return _tool_result_json(
                {"scope": project.name, "indexed": [stats.to_dict()]}
            )

        return _tool_result_text(f"Unknown tool: {name}")
    except indexer.StaleGenerationError as exc:
        return _tool_result_json({
            "error": str(exc),
            "stale": True,
            "requested_generation": exc.requested,
            "current_generation": exc.current,
            "message": "The generation is not current. Query again with query_wiki for a current passage reference.",
        })
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
    registry = await asyncio.get_running_loop().run_in_executor(_WORKERS, _get_registry)
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
        print("grimoire-mcp: MCP server for per-project wiki RAG.")
        print("Usage: grimoire-mcp   (runs as stdio MCP server)")
        print("       grimoire-mcp reindex [project|*]   (reindex without MCP)")
        print("       grimoire-mcp serve-http --port 8767 --token-file PATH")
        print("Env: WIKI_RAG_HOME, WIKI_RAG_PROJECTS_ROOT, WIKI_RAG_LOG")
        print("See README.md for OpenCode config and tool list.")
        _sys.exit(0)
    if len(_sys.argv) > 1 and _sys.argv[1] == "serve-http":
        import argparse
        from .shared_http import serve_http

        parser = argparse.ArgumentParser(prog="grimoire-mcp serve-http")
        parser.add_argument("--port", type=int, default=8767)
        parser.add_argument("--token-file", type=Path, required=True)
        args = parser.parse_args(_sys.argv[2:])
        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        _configure_logging()
        _get_registry()
        try:
            serve_http(app, port=args.port, token_file=args.token_file)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        return
    if len(_sys.argv) > 1 and _sys.argv[1] in {"--version", "-v"}:
        print(f"grimoire-mcp {SERVER_VERSION}")
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
            unchanged = sum(s.unchanged for s in stats)
            print(f"Reindexed {len(stats) - unchanged} projects; {unchanged} unchanged.")
            for s in stats:
                status = "unchanged" if s.unchanged else "rebuilt"
                print(f"  {s.project}: {status}, {s.files_indexed} files, {s.chunks} chunks")
        else:
            proj = reg.get(target)
            if not proj:
                print(f"Unknown project: {target}. Known: {', '.join(reg.names()[:5])}...")
                _sys.exit(1)
            if not proj.has_any_sources() and not _indexer.has_index(proj, reg.home):
                print(f"No sources for {target}")
                _sys.exit(1)
            s = _indexer.index_project(proj, reg.home)
            status = "Unchanged" if s.unchanged else "Reindexed"
            print(f"{status} {s.project}: {s.files_indexed} files, {s.chunks} chunks in {s.duration_s:.2f}s")
        _sys.exit(0)
    if len(_sys.argv) > 1:
        print(f"Unknown command: {_sys.argv[1]}. Use --help.", file=_sys.stderr)
        _sys.exit(2)
    try:
        import asyncio

        asyncio.run(_run())
    except KeyboardInterrupt:
        _sys.exit(0)


if __name__ == "__main__":
    main()
