"""Serve the existing MCP tools through one authenticated local process."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hmac
import os
from pathlib import Path
import stat

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
import uvicorn


def _read_token(path: Path) -> bytes:
    with path.open("rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("token file must be a regular file owned by the current user")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("token file must not allow group or other access; use chmod 600")
        token = stream.read(1025).strip()
    if not 32 <= len(token) <= 1024 or any(c < 33 or c > 126 for c in token):
        raise ValueError("token must contain 32 to 1024 printable ASCII characters without spaces")
    return token


class _AuthenticatedMCP:
    def __init__(self, manager: StreamableHTTPSessionManager, token: bytes):
        self.manager = manager
        self.token = token

    async def __call__(self, scope, receive, send):
        values = [value for name, value in scope["headers"] if name.lower() == b"authorization"]
        scheme, _, supplied = values[0].partition(b" ") if len(values) == 1 else (b"", b"", b"")
        if scheme.lower() != b"bearer" or not hmac.compare_digest(supplied, self.token):
            await Response(
                "Unauthorized", status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )(scope, receive, send)
            return
        await self.manager.asgi_app(scope, receive, send)


def serve_http(app: Server, *, port: int, token_file: Path) -> None:
    """Run one loopback listener. Client disconnects do not stop the server."""
    token = _read_token(token_file)
    hosts = [f"127.0.0.1:{port}", f"localhost:{port}"]
    manager = StreamableHTTPSessionManager(
        app=app,
        stateless=True,
        json_response=True,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[f"http://{host}" for host in hosts],
        ),
    )

    @asynccontextmanager
    async def lifespan(_application):
        async with manager.run():
            yield

    http_app = Starlette(
        routes=[Route("/mcp", _AuthenticatedMCP(manager, token), methods=["GET", "POST", "DELETE"])],
        lifespan=lifespan,
    )
    uvicorn.run(
        http_app, host="127.0.0.1", port=port, workers=1,
        access_log=False, proxy_headers=False, timeout_graceful_shutdown=15,
    )
