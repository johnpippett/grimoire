"""Exercise bounded wiki search and passage reads through a real MCP client.

The test uses a temporary projects root and index home. It starts the stdio MCP
server as a child process and removes the fixture after it writes JSON evidence.

Run with the locked Grimoire environment:
    python grimoire-mcp/tests/e2e_search.py --output /tmp/grimoire-search-e2e.json
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "grimoire-mcp"


@contextmanager
def step(steps: list[dict[str, Any]], name: str):
    start = time.monotonic()
    try:
        yield
    except BaseException as exc:
        steps.append({
            "name": name,
            "result": "failed",
            "seconds": round(time.monotonic() - start, 3),
            "error": f"{type(exc).__name__}: {exc}",
        })
        raise
    else:
        steps.append({"name": name, "result": "passed", "seconds": round(time.monotonic() - start, 3)})


def text_result(result: Any) -> str:
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


@asynccontextmanager
async def mcp_session(projects: Path, home: Path):
    env = os.environ.copy()
    env.update({
        "WIKI_RAG_PROJECTS_ROOT": str(projects),
        "WIKI_RAG_HOME": str(home),
        "WIKI_RAG_LOG": str(home.parent / "server.log"),
        "PYTHONPATH": str(PACKAGE / "src"),
        "PYTHONUNBUFFERED": "1",
    })
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "wiki_rag.server"],
        env=env,
        cwd=PACKAGE,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def run(output: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    failure: str | None = None
    temp = tempfile.TemporaryDirectory(prefix="grimoire-search-e2e-")
    base = Path(temp.name)
    projects = base / "projects"
    home = base / "home"
    wiki = projects / "fixture" / "wiki"
    wiki.mkdir(parents=True)
    long_source = wiki / "long-passage.md"
    long_source.write_text("# Long passage\n" + "passagemarker " * 8000, encoding="utf-8")
    for number in range(30):
        body = f"sharedneedle item {number}. " + ("Evidence details support safe operations. " * 45)
        (wiki / f"note-{number:02}.md").write_text(f"# Note {number}\n\n{body}", encoding="utf-8")
    try:
        async with mcp_session(projects, home) as session:
            with step(steps, "discover the search and passage MCP tools"):
                tool_list = (await session.list_tools()).tools
                names = sorted(tool.name for tool in tool_list)
                assert names == ["list_projects", "query_wiki", "read_wiki_passage", "reindex_project"]
                passage_tool = next(tool for tool in tool_list if tool.name == "read_wiki_passage")
                properties = passage_tool.inputSchema["properties"]
                assert properties["chunk_id"]["pattern"] == "^[0-9a-f]{64}$"
                assert properties["generation"]["pattern"] == "^[0-9a-f]{32}$"
                results["tools"] = names
                results["passage_reference_patterns"] = {
                    "generation": properties["generation"]["pattern"],
                    "chunk_id": properties["chunk_id"]["pattern"],
                }

            with step(steps, "build the disposable fixture index"):
                indexed = await session.call_tool("reindex_project", {"project": "fixture"})
                assert not indexed.isError and "fixture" in text_result(indexed).lower()

            with step(steps, "return no hits for an unmatched query"):
                no_match_text = text_result(await session.call_tool(
                    "query_wiki", {"project": "fixture", "question": "unfindablezymotif", "top_k": 25}
                ))
                no_match = json.loads(no_match_text)
                assert no_match["results"] == []
                assert no_match["omitted_hits"] == 0
                results["no_match"] = {"response_chars": len(no_match_text), "result_count": 0}

            with step(steps, "bound query output and record omitted hits"):
                query_text = text_result(await session.call_tool(
                    "query_wiki", {"project": "fixture", "question": "sharedneedle", "top_k": 25}
                ))
                query = json.loads(query_text)
                assert len(query_text) <= 8000
                assert query["omitted_hits"] > 0
                assert query["results"]
                assert all(hit["score"] > 0 for hit in query["results"])
                assert all(hit["generation"] and hit["chunk_id"] and hit["indexed_at"] for hit in query["results"])
                assert all(hit["wiki_roots"] == [str(wiki)] for hit in query["results"])
                assert any(hit["excerpt_truncated"] for hit in query["results"])
                results["bounded_query"] = {
                    "response_chars": len(query_text),
                    "returned_hits": len(query["results"]),
                    "omitted_hits": query["omitted_hits"],
                    "truncated_excerpts": sum(hit["excerpt_truncated"] for hit in query["results"]),
                }

            with step(steps, "recover an incomplete passage through offset pages"):
                passage_query_text = text_result(await session.call_tool(
                    "query_wiki", {"project": "fixture", "question": "passagemarker", "top_k": 1}
                ))
                passage_query = json.loads(passage_query_text)
                assert passage_query["results"]
                reference = passage_query["results"][0]
                offset = 0
                pages: list[str] = []
                page_chars: list[int] = []
                first_complete: bool | None = None
                while True:
                    page_text = text_result(await session.call_tool("read_wiki_passage", {
                        "project": "fixture",
                        "generation": reference["generation"],
                        "chunk_id": reference["chunk_id"],
                        "offset": offset,
                    }))
                    assert len(page_text) <= 8000
                    page = json.loads(page_text)
                    assert page["offset"] == offset
                    assert page["next_offset"] == offset + len(page["text"])
                    if first_complete is None:
                        first_complete = page["complete"]
                    pages.append(page["text"])
                    page_chars.append(len(page_text))
                    if page["complete"]:
                        break
                    assert page["next_offset"] > offset
                    offset = page["next_offset"]
                recovered = "".join(pages)
                assert first_complete is False
                assert len(recovered) == page["passage_length"]
                assert recovered.startswith(reference["text"])
                results["passage_recovery"] = {
                    "chunk_id": reference["chunk_id"],
                    "passage_chars": len(recovered),
                    "page_count": len(pages),
                    "page_response_chars": page_chars,
                    "first_page_complete": first_complete,
                    "complete": True,
                }

            with step(steps, "mark old passage references stale after reindex"):
                long_source.write_text("# Updated long passage\n" + "newpassagemarker " * 8000, encoding="utf-8")
                refreshed = await session.call_tool("reindex_project", {"project": "fixture"})
                assert not refreshed.isError
                stale_text = text_result(await session.call_tool("read_wiki_passage", {
                    "project": "fixture",
                    "generation": reference["generation"],
                    "chunk_id": reference["chunk_id"],
                }))
                stale = json.loads(stale_text)
                assert stale["stale"] is True
                assert "query again" in stale["message"].lower()
                results["stale_reference"] = stale
    except BaseException as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        temp.cleanup()

    report = {
        "result": "passed" if failure is None else "failed",
        "setup": {
            "transport": "stdio MCP",
            "server_command": [sys.executable, "-m", "wiki_rag.server"],
            "projects_root": str(projects),
            "wiki_path": str(wiki),
            "index_home": str(home),
            "temporary_home_removed": True,
            "fixture": "30 search notes and one 8,000-token passage source",
        },
        "steps": steps,
        "results": results,
        "failure": failure,
        "rerun": f"{sys.executable} {Path(__file__).resolve()} --output {output}",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="write repeatable test evidence JSON here")
    args = parser.parse_args()
    report = asyncio.run(run(args.output.resolve()))
    print(f"search E2E {report['result']}; evidence: {args.output.resolve()}")
    if report["failure"]:
        failed = next((item["name"] for item in report["steps"] if item["result"] == "failed"), "setup")
        print(f"failed at: {failed}")
        return 1
    print(f"steps passed: {len(report['steps'])}; passage pages: {report['results']['passage_recovery']['page_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
