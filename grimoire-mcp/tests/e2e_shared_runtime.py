"""Real-MCP test for one authenticated, shared Grimoire HTTP runtime.

Failure-mode analysis, written before the test:
- The HTTP CLI is missing, binds the wrong address, or hangs at startup.
- Missing, wrong, or invalid bearer credentials are accepted.
- A valid token bypasses Host or Origin checks.
- MCP initialization, tool discovery, indexing, or retrieval fails.
- Concurrent clients launch extra server processes or receive different state.
- A second listener binds the occupied port, or restart loses the saved index.
- A timeout or assertion leaves a server process running or exposes the token.

Run from the repository root with:
    grimoire-mcp/.venv/bin/python grimoire-mcp/tests/e2e_shared_runtime.py \
        --output /tmp/grimoire-shared-runtime-evidence.json

The script creates a temporary projects root, index home, and mode-0600 token
file. It records setup, steps, durations, server PIDs, child PIDs, and RSS in
the JSON evidence file. It does not record or print token values.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "grimoire-mcp"
CLI = PACKAGE / ".venv" / "bin" / "grimoire-mcp"
KNOWN_FACT = "cobalt otter 742"
CLIENT_COUNT = 12
INIT_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "grimoire-e2e", "version": "1"},
    },
}


class BearerToken(httpx.Auth):
    def __init__(self, token: str) -> None:
        self._token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


@contextmanager
def step(steps: list[dict[str, Any]], name: str):
    start = time.monotonic()
    try:
        yield
    except BaseException as exc:
        steps.append({"name": name, "result": "failed", "seconds": round(time.monotonic() - start, 3), "error": f"{type(exc).__name__}: {exc}"})
        raise
    else:
        steps.append({"name": name, "result": "passed", "seconds": round(time.monotonic() - start, 3)})


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def launch(port: int, token_file: Path, env: dict[str, str], processes: list[subprocess.Popen]) -> subprocess.Popen:
    proc = subprocess.Popen(
        [str(CLI), "serve-http", "--port", str(port), "--token-file", str(token_file)],
        cwd=PACKAGE,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    processes.append(proc)
    return proc


def wait_for_listener(proc: subprocess.Popen, port: int, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = proc.poll()
        if code is not None:
            raise RuntimeError(f"server exited before HTTP listener opened (exit {code})")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError("server did not open its HTTP listener before timeout")


def listener_addresses(port: int) -> tuple[list[str], bool]:
    """Return matching IPv4 listeners and whether IPv6 also listens on port."""
    table = Path("/proc/net/tcp")
    if not table.exists():
        raise RuntimeError("this test needs Linux /proc to verify bind and child state")
    addresses: list[str] = []
    for row in table.read_text().splitlines()[1:]:
        fields = row.split()
        local, state = fields[1], fields[3]
        host_hex, port_hex = local.split(":")
        if state == "0A" and int(port_hex, 16) == port:
            addresses.append(socket.inet_ntoa(bytes.fromhex(host_hex)[::-1]))
    tcp6 = Path("/proc/net/tcp6")
    ipv6_listener = False
    if tcp6.exists():
        for row in tcp6.read_text().splitlines()[1:]:
            fields = row.split()
            if fields[3] == "0A" and int(fields[1].split(":")[1], 16) == port:
                ipv6_listener = True
    return addresses, ipv6_listener


def child_pids(pid: int) -> list[int]:
    tasks = Path(f"/proc/{pid}/task")
    if not tasks.is_dir():
        raise RuntimeError("server process ended before child-process check")
    found: set[int] = set()
    for task in tasks.iterdir():
        children = task / "children"
        if children.exists():
            found.update(int(value) for value in children.read_text().split())
    return sorted(found)


def rss_kib(pid: int) -> int | None:
    status = Path(f"/proc/{pid}/status")
    if not status.exists():
        return None
    for line in status.read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


def text_result(result: Any) -> str:
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


@asynccontextmanager
async def mcp_client(url: str, token: str):
    async with httpx.AsyncClient(
        auth=BearerToken(token), timeout=5.0, trust_env=False
    ) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (
            read_stream, write_stream, get_session_id
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                assert get_session_id() is None, "stateless HTTP must not assign an MCP session id"
                yield session


async def authorized_request_checks(url: str, token: str) -> dict[str, int]:
    base = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
        missing = await client.post(url, headers=base, json=INIT_BODY)
        wrong = await client.post(url, headers={**base, "Authorization": "Bearer wrong-test-value"}, json=INIT_BODY)
        assert missing.status_code in {401, 403}, "missing bearer token was not rejected"
        assert wrong.status_code in {401, 403}, "wrong bearer token was not rejected"
        bad_origin = await client.post(url, headers={**base, "Authorization": f"Bearer {token}", "Origin": "https://invalid.example"}, json=INIT_BODY)
        bad_host = await client.post(url, headers={**base, "Authorization": f"Bearer {token}", "Host": "invalid.example"}, json=INIT_BODY)
        assert bad_origin.status_code == 403, "invalid Origin was not rejected"
        assert bad_host.status_code == 421, "invalid Host was not rejected"
        return {
            "missing_token": missing.status_code,
            "wrong_token": wrong.status_code,
            "bad_origin": bad_origin.status_code,
            "bad_host": bad_host.status_code,
        }


async def query_fact(url: str, token: str) -> str:
    async with mcp_client(url, token) as session:
        result = await session.call_tool("query_wiki", {"project": "fixture", "question": "What is the stored fixture phrase?"})
        assert not result.isError, "wiki query returned an MCP error"
        answer = text_result(result).lower()
        assert KNOWN_FACT in answer, "query did not return the known fixture fact"
        return answer


async def concurrent_clients(url: str, token: str) -> int:
    async def client_query(_: int) -> None:
        async with mcp_client(url, token) as session:
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {"list_projects", "query_wiki", "read_wiki_passage", "reindex_project"}
            result = await session.call_tool("query_wiki", {"project": "fixture", "question": "What is the stored fixture phrase?"})
            assert KNOWN_FACT in text_result(result).lower()
    await asyncio.wait_for(asyncio.gather(*(client_query(i) for i in range(CLIENT_COUNT))), timeout=20.0)
    return CLIENT_COUNT


def stop_owned(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=4.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2.0)


async def run(output: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    processes: list[subprocess.Popen] = []
    pids: list[int] = []
    memory: list[dict[str, Any]] = []
    failure: str | None = None
    setup: dict[str, Any] = {"command": "grimoire-mcp serve-http --port PORT --token-file PATH", "bind": "127.0.0.1 only", "transport": "stateless Streamable HTTP at /mcp", "fixture_fact": KNOWN_FACT, "concurrent_clients": CLIENT_COUNT, "token_recorded": False}
    temp = tempfile.TemporaryDirectory(prefix="grimoire-e2e-")
    base = Path(temp.name)
    projects = base / "projects"
    wiki = projects / "fixture" / "wiki"
    home = base / "home"
    token_file = base / "token"
    wiki.mkdir(parents=True)
    (wiki / "fact.md").write_text(f"# Fixture\n\nStored phrase: {KNOWN_FACT}.\n", encoding="utf-8")
    token = secrets.token_urlsafe(32)
    hidden_tokens = [token, "wrong-test-value"]
    token_file.write_text(token, encoding="ascii")
    token_file.chmod(0o600)
    env = os.environ.copy()
    env.update({"WIKI_RAG_HOME": str(home), "WIKI_RAG_PROJECTS_ROOT": str(projects), "WIKI_RAG_LOG": str(base / "server.log")})
    port = free_port()
    setup.update({"projects_root": str(projects), "wiki_path": str(wiki / "fact.md"), "port": port, "token_file_mode": "0600"})
    current: subprocess.Popen | None = None
    try:
        with step(steps, "start one HTTP server"):
            current = launch(port, token_file, env, processes)
            pids.append(current.pid)
            wait_for_listener(current, port)
            memory.append({"pid": current.pid, "rss_kib": rss_kib(current.pid)})
        url = f"http://127.0.0.1:{port}/mcp"
        with step(steps, "bind only to IPv4 loopback"):
            ipv4, ipv6 = listener_addresses(port)
            assert ipv4 == ["127.0.0.1"] and not ipv6, f"unexpected listeners: {ipv4}, ipv6={ipv6}"
        with step(steps, "reject missing, wrong, Host, and Origin credentials"):
            results["http_security_statuses"] = await authorized_request_checks(url, token)
        with step(steps, "initialize MCP and list all four tools"):
            async with mcp_client(url, token) as session:
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {"list_projects", "query_wiki", "read_wiki_passage", "reindex_project"}
                results["tool_names"] = sorted(tool.name for tool in tools.tools)
        with step(steps, "reindex the temporary wiki fixture"):
            async with mcp_client(url, token) as session:
                result = await session.call_tool("reindex_project", {"project": "fixture"})
                assert not result.isError and "fixture" in text_result(result).lower()
        with step(steps, "query the indexed known fact"):
            await query_fact(url, token)
        with step(steps, f"run {CLIENT_COUNT} concurrent independent MCP clients on one PID"):
            pid = current.pid
            before_children = child_pids(pid)
            assert not before_children, f"server started child processes: {before_children}"
            count = await concurrent_clients(url, token)
            assert current.poll() is None and current.pid == pid, "shared server PID changed or exited"
            after_children = child_pids(pid)
            assert not after_children, f"concurrent clients caused server child processes: {after_children}"
            results["concurrent_process_check"] = {
                "clients": count,
                "server_pid_before": pid,
                "server_pid_after": current.pid,
                "server_alive_after_clients": current.poll() is None,
                "children_before": before_children,
                "children_after": after_children,
            }
            memory.append({"pid": pid, "rss_kib": rss_kib(pid)})
        with step(steps, "reject a second listener on the occupied port"):
            second = launch(port, token_file, env, processes)
            pids.append(second.pid)
            try:
                second.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                raise AssertionError("second server stayed alive on the occupied port")
            assert second.returncode != 0, "second server did not fail on the occupied port"
            active_listeners = listener_addresses(port)[0]
            assert current.poll() is None and len(active_listeners) == 1
            results["occupied_port"] = {
                "second_server_pid": second.pid,
                "second_server_exit_code": second.returncode,
                "active_ipv4_listeners": active_listeners,
            }
        with step(steps, "reject an invalid token file at startup"):
            bad_files = [("short token", "short", 0o600),
                         ("permissive mode", secrets.token_urlsafe(32), 0o644)]
            results["invalid_token_startup"] = {}
            for label, value, mode in bad_files:
                hidden_tokens.append(value)
                bad_file = base / f"invalid-token-{label.replace(' ', '-')}"
                bad_file.write_text(value, encoding="ascii")
                bad_file.chmod(mode)
                invalid = launch(free_port(), bad_file, env, processes)
                pids.append(invalid.pid)
                try:
                    invalid.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    stop_owned(invalid)
                    raise AssertionError(f"server accepted invalid token case: {label}")
                assert invalid.returncode != 0, f"invalid token case did not fail startup: {label}"
                results["invalid_token_startup"][label] = invalid.returncode
        with step(steps, "restart and query the persisted index without reindexing"):
            old_pid = current.pid
            stop_owned(current)
            current = launch(port, token_file, env, processes)
            pids.append(current.pid)
            wait_for_listener(current, port)
            assert current.pid != old_pid, "restart reused the recorded server PID"
            memory.append({"pid": current.pid, "rss_kib": rss_kib(current.pid)})
            await query_fact(url, token)
            results["persisted_index_restart"] = {
                "previous_server_pid": old_pid,
                "restart_server_pid": current.pid,
                "query_fact_found": True,
                "reindexed_after_restart": False,
            }
    except BaseException as exc:
        message = str(exc)
        for value in hidden_tokens:
            message = message.replace(value, "[REDACTED]")
        failure = f"{type(exc).__name__}: {message}"
    finally:
        for proc in processes:
            stop_owned(proc)
        temp.cleanup()
    report = {
        "result": "passed" if failure is None else "failed",
        "setup": setup,
        "steps": steps,
        "results": results,
        "failure": failure,
        "server_pids": pids,
        "memory": memory,
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
    print(f"shared-runtime E2E {report['result']}; evidence: {args.output.resolve()}")
    if report["failure"]:
        print(f"failed at: {report['steps'][-1]['name'] if report['steps'] else 'setup'}")
        return 1
    print(f"steps passed: {len(report['steps'])}; server PIDs: {report['server_pids']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
