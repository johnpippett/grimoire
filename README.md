<p align="center">
  <img src="https://github.com/johnpippett/grimoire/blob/main/logo.jpg?raw=true" alt="Grimoire" width="60%" />
</p>

<h1 align="center">Grimoire — Agent Project Library</h1>

**A project library that every AI coding agent reads from and writes to — durable, searchable, and living beside the code.**

Grimoire is a three-layer system that turns your project's `wiki/` folder into a living library agents consult before they act and contribute to after meaningful changes. Cross-project search comes from a lightweight MCP server.

---

## The Three Layers

```
┌──────────────────────────────────────────────────┐
│  Layer 3: grimoire-mcp (cross-project search)    │
│  BM25 over all project wikis — plug into any     │
│  agent harness (Claude, Cursor, OpenCode, etc.)  │
├──────────────────────────────────────────────────┤
│  Layer 2: Agent Contract (AGENTS.md)             │
│  One self-contained file: bootstrap, Grimoire     │
│  Gate, pre-work checklist, wiki update workflow.  │
├──────────────────────────────────────────────────┤
│  Layer 1: The Library (wiki/)                    │
│  Decimal-numbered markdown notes.                │
│  What changed, why, how to verify, rollback.     │
└──────────────────────────────────────────────────┘
```

### Layer 1 — The Library

A `wiki/` directory in your project root with decimal-numbered markdown notes:

```
wiki/
├── README.md                          # Numbering system + agent rules
├── 10-19 Conversations & Decisions/
│   ├── 11 Key Decisions/              # 11.01, 11.02, ...
│   └── 12 Session Logs/               # 12.01 Session Log Index, 12.02, ...
├── 20-29 Implementation & Operations/
│   ├── 21 Implementation Notes/       # 21.01, 21.02, ...
│   └── 22 Workflows/                  # 22.01, 22.02, ...
├── 30-39 Integrations & Tooling/
│   ├── 31 Tool Configs/               # 31.01, 31.02, ...
│   └── 32 Integration Notes/          # 32.01, ...
└── 90-99 Archive/                     # Retired notes
    └── 91 Historical Scripts/
```

Each note is short and covers: **what changed, why it changed, how to verify, rollback notes when relevant.**

### Layer 2 — The Agent Contract

One file tells every agent everything it needs:

- **`AGENTS.md`** — The single entry point. Contains bootstrap instructions, the "Grimoire Gate" contract (read wiki before editing, write to it after), a pre-work checklist, the wiki update workflow, and rules for when to skip. Self-contained — no other files required.

A **`setup.sh`** script bootstraps the `wiki/` directory into any project in one command, for both humans and agents.

### Layer 3 — Cross-Project Search (grimoire-mcp)

A standalone [MCP](https://modelcontextprotocol.io/) server that indexes all your project wikis with BM25 (no embeddings, no GPU, deterministic) and exposes three tools to agents:

- `list_projects` — discover available projects and their wiki status
- `query_wiki` — search a project's wiki with natural language
- `reindex_project` — rebuild the index after wiki changes

---

## Quick Start

### 1. Add the library to your project

Run the bootstrap script from within the grimoire repo:

```bash
./setup.sh /path/to/your-project
```

Or, if you're already in your project directory, copy the template manually:

```bash
cp -r /path/to/grimoire/wiki-template wiki
```

### 2. Add the agent contract

Copy `AGENTS.md` into your project root. That's it — it's self-contained:

```bash
cp /path/to/grimoire/AGENTS.md your-project/
```

Customize the **Scope** section with a one-line description of your project.

For harnesses that don't natively read `AGENTS.md`, rename it to the convention
that harness expects: `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`,
`AIDER.md`, etc.

### 3. (Optional) Set up cross-project search

The `grimoire-mcp/` server lets agents search across all your projects. See its [README](grimoire-mcp/README.md) for setup.

```bash
cd grimoire-mcp
uv sync
```

Then add to your agent's MCP config:

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

Set `WIKI_RAG_PROJECTS_ROOT` to wherever you keep your projects (default: `~/projects`).

### 4. Start using it

The next time an agent starts work in your project, it reads `AGENTS.md` and:

1. If `wiki/` doesn't exist → runs bootstrap (from the Bootstrap section)
2. Follows the Pre-Work Checklist → reads wiki/ for context
3. Does the work
4. Follows the Wiki Update Workflow → creates or updates a wiki note
5. Reports which note was changed

That's it. One file. No harness-specific features needed.

---

## How Agents Actually Use This

Here's the flow on any meaningful change:

```
Agent starts work
  └─ Reads AGENTS.md
       ├─ If wiki/ doesn't exist: runs bootstrap (setup.sh or manual copy)
       ├─ Reads wiki/README.md for numbering scheme
       └─ Scans wiki/ for relevant project context

Agent does work (edit code, change config, update deps, etc.)

Agent finishes
  └─ Follows Wiki Update Workflow in AGENTS.md
       ├─ Checks wiki/ for existing notes on the topic
       ├─ Updates existing note OR creates next decimal note
       ├─ Updates 12.01 Session Log Index
       └─ Reports: "Updated wiki/20-29.../21.03 Thing I Changed.md"
```

A week later, another agent starts work. It reads the wiki, finds `21.03`, and
immediately understands what was done and why — no chat history needed.

---

## Philosophy

### Why not just use chat history?

Chat sessions are ephemeral. They die when the context window fills, when you switch models, or when you start a new session. The wiki is **durable project knowledge** — it lives in the repo beside the code.

### Why decimal numbering?

Simple, sortable, and unambiguous. `11.01` comes before `11.02`. No date stamps, no titles in filenames — just numbers. The folder structure provides the topic category. This makes it trivial for agents to find the next available number and for humans to scan.

### Why BM25 instead of embeddings?

- **Zero dependencies.** No embedding model to download, no GPU needed, no first-run stall.
- **Deterministic.** Same query always returns the same results. Easy to debug.
- **Fast.** Sub-second queries on wikis with hundreds of files.
- **Local only.** Nothing leaves your machine.

### Why per-project wikis instead of one big knowledge base?

Project knowledge belongs beside the project. When you move, archive, or share a project, its wiki goes with it. No central database to maintain or migrate.

---

## Files in This Kit

| File | Purpose |
|---|---|
| `README.md` | This guide |
| `AGENTS.md` | **Single entry point** — bootstrap, Grimoire Gate, pre-work checklist, wiki update workflow (self-contained, no other files needed) |
| `setup.sh` | Bootstrap script — copies `wiki-template/` into any project in one command |
| `wiki-template/` | Drop-in wiki folder structure |
| `grimoire-mcp/` | Standalone MCP server for cross-project search |
| `skills/` | Optional — this repo's own internal skills (not needed by consumer projects; everything is inlined in `AGENTS.md`) |

---

## Adopting Incrementally

You don't need all three layers on day one:

1. **Start with just the wiki folder.** Even without agent enforcement, having a place to write down what changed and why is valuable. Run `./setup.sh` or copy `wiki-template/` manually.
2. **Add AGENTS.md.** This is the force-multiplier — agents start reading and writing the library automatically. One file, self-contained.
3. **Add grimoire-mcp when you have multiple projects.** Cross-project search becomes useful when you have 5+ wikis and agents need to find information across them.

---

## Compatible Agent Harnesses

The system is harness-agnostic. **`AGENTS.md` is the only file an agent needs to
read** — it contains bootstrap, intake, and update workflows in one place.

Works with any agent that reads project-level instruction files:

- **Claude Code** (reads `CLAUDE.md` — rename or symlink `AGENTS.md`)
- **Cursor** (reads `.cursorrules` — rename or symlink)
- **Codex Desktop** (reads `AGENTS.md` natively)
- **OpenCode** (reads `AGENTS.md` natively)
- **Aider** (reads `AIDER.md` or `CONVENTIONS.md` — rename or symlink)
- **GitHub Copilot** (reads `.github/copilot-instructions.md` — rename or symlink)
- **Reasonix** (reads `AGENTS.md` natively)

For harnesses that don't natively read `AGENTS.md`, rename it to the convention
file that harness expects, or create a symlink.

The `grimoire-mcp` server works with any harness that supports MCP tools (Claude,
Cursor, OpenCode, Grok, etc.).

### How a user hands this to any agent

The user gives an agent the grimoire repo and says:

> "Set up Grimoire in my project at `/path/to/my-project`."

The agent reads `AGENTS.md`, finds the **Bootstrap** section, runs `./setup.sh`,
and follows the Pre-Work Checklist. No harness-specific features needed.

---

## License

MIT. Use it, fork it, adapt it.
