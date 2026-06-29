# Agent Wiki System — Starter Kit

**Give every AI coding agent durable, searchable, project-local memory that survives chat sessions.**

This is a three-layer system that turns your project's `wiki/` folder into the canonical memory for every agent that touches your code. Agents read the wiki before they act, write to it when they make meaningful changes, and can search across all your projects with a lightweight MCP server.

---

## The Three Layers

```
┌──────────────────────────────────────────────────┐
│  Layer 3: wiki-rag-mcp (cross-project search)    │
│  BM25 over all project wikis — plug into any     │
│  agent harness (Claude, Cursor, OpenCode, etc.)  │
├──────────────────────────────────────────────────┤
│  Layer 2: Agent Contract (AGENTS.md + skills/)   │
│  Tells every agent: read the wiki before acting, │
│  write to it after meaningful changes.           │
├──────────────────────────────────────────────────┤
│  Layer 1: Wiki folder (wiki/)                    │
│  Decimal-numbered markdown notes.                │
│  What changed, why, how to verify, rollback.     │
└──────────────────────────────────────────────────┘
```

### Layer 1 — The Wiki Folder

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

Two files tell every agent to treat the wiki as mandatory:

- **`AGENTS.md`** — Contains the "Wiki Documentation Gate": agents must read the wiki before editing, write to it after meaningful changes, and report what they changed (or why they didn't).
- **`skills/project-wiki-memory/SKILL.md`** — The playbook agents follow: inspect → update/create → report.
- **`skills/project-intake/SKILL.md`** — Orientation: read AGENTS.md, README.md, skills/, and wiki/ before acting.

### Layer 3 — Cross-Project Search (wiki-rag-mcp)

A standalone [MCP](https://modelcontextprotocol.io/) server that indexes all your project wikis with BM25 (no embeddings, no GPU, deterministic) and exposes three tools to agents:

- `list_projects` — discover available projects and their wiki status
- `query_wiki` — search a project's wiki with natural language
- `reindex_project` — rebuild the index after wiki changes

---

## Quick Start

### 1. Add the wiki to your project

Copy `wiki-template/` into your project root as `wiki/`:

```bash
cp -r wiki-template/ my-project/wiki/
```

### 2. Add the agent contract

Copy `AGENTS.md` and `skills/` into your project root:

```bash
cp AGENTS.md my-project/
cp -r skills/ my-project/skills/
```

Customize `AGENTS.md` with any project-specific rules above the Wiki Documentation Gate section.

### 3. (Optional) Set up cross-project search

The `wiki-rag-mcp/` server lets agents search across all your projects. See its [README](wiki-rag-mcp/README.md) for setup.

```bash
cd wiki-rag-mcp
uv sync
```

Then add to your agent's MCP config:

```json
{
  "mcpServers": {
    "wiki-rag-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/wiki-rag-mcp", "wiki-rag-mcp"]
    }
  }
}
```

Set `WIKI_RAG_PROJECTS_ROOT` to wherever you keep your projects (default: `~/projects`).

### 4. Start using it

The next time an agent starts work in your project, it will:
1. Read `AGENTS.md` → see the Wiki Documentation Gate
2. Run the `project-intake` skill → read wiki/ for context
3. Do the work
4. Run the `project-wiki-memory` skill → create or update a wiki note
5. Report which note was changed

---

## How Agents Actually Use This

Here's the flow on any meaningful change:

```
Agent starts work
  └─ skills/project-intake fires
       └─ Reads AGENTS.md, README.md, wiki/README.md, relevant wiki notes
            └─ Agent now has project context

Agent does work (edit code, change config, update deps, etc.)

Agent finishes
  └─ skills/project-wiki-memory fires
       └─ Checks wiki/ for existing notes on the topic
       └─ Updates existing note OR creates next decimal note
       └─ Updates 12.01 Session Log Index
       └─ Reports: "Updated wiki/20-29.../21.03 Thing I Changed.md"
```

A week later, another agent starts work. It reads the wiki, finds `21.03`, and immediately understands what was done and why — no chat history needed.

---

## Philosophy

### Why not just use chat history?

Chat sessions are ephemeral. They die when the context window fills, when you switch models, or when you start a new session. The wiki is **durable project memory** — it lives in the repo beside the code.

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
| `AGENTS.md` | Template agent instructions with Wiki Documentation Gate |
| `wiki-template/` | Drop-in wiki folder structure |
| `skills/project-wiki-memory/SKILL.md` | Agent playbook for wiki updates |
| `skills/project-intake/SKILL.md` | Agent playbook for project orientation |
| `wiki-rag-mcp/` | Standalone MCP server for cross-project search |

---

## Adopting Incrementally

You don't need all three layers on day one:

1. **Start with just the wiki folder.** Even without agent enforcement, having a place to write down what changed and why is valuable.
2. **Add AGENTS.md + skills.** This is the force-multiplier — agents start reading and writing the wiki automatically.
3. **Add wiki-rag-mcp when you have multiple projects.** Cross-project search becomes useful when you have 5+ wikis and agents need to find information across them.

---

## Compatible Agent Harnesses

The system is model-agnostic and harness-agnostic. It works with any agent that reads project-level instruction files:

- **Claude Code** (reads `CLAUDE.md`)
- **Cursor** (reads `.cursorrules` or project instructions)
- **Codex Desktop** (reads `AGENTS.md`)
- **OpenCode** (reads `AGENTS.md`)
- **Aider** (reads `AIDER.md` or convention files)
- **GitHub Copilot** (reads `.github/copilot-instructions.md`)

For harnesses that don't natively read `AGENTS.md`, rename it to the convention file that harness expects, or symlink it.

The `wiki-rag-mcp` server works with any harness that supports MCP tools (Claude, Cursor, OpenCode, Grok, etc.).

---

## License

MIT. Use it, fork it, adapt it.
