# Shared local MCP runtime

Use one local server when several agents need Grimoire search.
Streamable HTTP clients connect to the same process, worker pool, and BM25 cache.
The server binds only to `127.0.0.1`. Every request needs a bearer token.
The shared runtime keeps the existing index format. The modernization adds
`read_wiki_passage` to the MCP tool list. The shared process serves this tool
after it starts the modernized source.

The default stdio command remains available for clients that require it.
Each stdio client starts a separate Python process.
Use the HTTP connection to prevent this duplication.
This service uses BM25 search. It does not load an embedding model.

## Install the user service

1. Install the locked dependencies from `grimoire-mcp/`:

   ```bash
   uv sync --locked
   ```

2. Create a private token file. This command does not display the token:

   ```bash
   python - <<'PY'
   import os
   import secrets
   from pathlib import Path
   target = Path.home() / '.wiki-rag' / 'mcp-token'
   target.parent.mkdir(parents=True, exist_ok=True)
   fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
   with os.fdopen(fd, 'w') as stream:
       stream.write(secrets.token_urlsafe(32) + '\n')
   PY
   ```

3. Copy `ops/systemd/grimoire-mcp.service.in` to `~/.config/systemd/user/grimoire-mcp.service`.
4. Replace the template fields with absolute paths and an unused local port.
5. Set the project root and index home to the values used by your refresh job.
6. Start the service:

   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now grimoire-mcp.service
   systemctl --user status grimoire-mcp.service
   ```

The user service starts at login. It restarts after a failure.
Confirm readiness with an authenticated MCP call before connecting clients.
Systemd can report the service active before its port opens.
The existing refresh timer remains separate. Its batch process exits after indexing.
File locks and atomic index publication coordinate refresh with active queries.

## Connect a client

Use `http://127.0.0.1:8767/mcp` when the service port is `8767`.
Set the HTTP `Authorization` header to `Bearer ` followed by the token file contents.
Configure each client to use this endpoint instead of the stdio command.
Keep credentials in private client settings. Never add them to the repository.

Codex supports this configuration in its private `config.toml`:

```toml
[mcp_servers.grimoire-mcp]
url = "http://127.0.0.1:8767/mcp"
http_headers = { Authorization = "Bearer REPLACE_WITH_LOCAL_TOKEN" }
```

Remove the old `command`, `args`, and Grimoire `env` entries from that registration.
Set the configuration file permissions to `0600`.
Restart clients that retain their old MCP connections.
Other clients can use the same endpoint and token through their Streamable HTTP settings.

For a foreground server, use this command:

```bash
grimoire-mcp serve-http --port 8767 --token-file "$HOME/.wiki-rag/mcp-token"
```

Only one process can bind to the selected address and port.
Client disconnects do not stop the shared process.
Restart the service after changing its token file or project environment.

## End-to-end verification

Run the test from the repository root:

```bash
grimoire-mcp/.venv/bin/python grimoire-mcp/tests/e2e_shared_runtime.py --output /tmp/grimoire-shared-runtime.json
```

The test uses temporary projects, indexes, credentials, and a local port.
Its JSON report records the setup, steps, results, timings, and process measurements.
The test checks concurrent MCP clients, authentication, search, indexing, and server restart.

For live memory measurements, use proportional set size (PSS) from `/proc/PID/smaps_rollup`.
Do not add process RSS values as an estimate of physical RAM use.
`SwapPss` measures logical swap pages. Compressed zram uses less physical RAM than this value.

## Rollback

Restore the previous Grimoire MCP client registration from its private backup.
Restart that client. Then stop and disable `grimoire-mcp.service`.
The wiki files, indexes, and refresh timer do not need restoration.
The stdio configuration will again permit one Python process per client.
