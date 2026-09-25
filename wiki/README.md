# Grimoire project wiki

## Project orientation

Grimoire keeps project knowledge in repository-owned Markdown wikis.
Standalone and coordinating agents read relevant notes before work. A
delegated worker can use sufficient wiki context and source paths from its
coordinator, then read more when needed. Coordinators own the final wiki
updates. `grimoire-mcp` searches registered project wikis with local BM25
indexes. File tools remain sufficient when MCP is unavailable.

Use these terms consistently:

- **Project wiki:** The `wiki/` directory in a project checkout. It is the
  source of project decisions and work notes.
- **Index generation:** A published copy of indexed wiki text. Search results
  refer to this copy until the next refresh.
- **Shared runtime:** The local HTTP MCP service used by multiple clients.
  Legacy stdio clients can still run separate processes.

Current state: The modernization is deployed in the main checkout and shared
service. Registered project guidance has been migrated. Read the
[specification](../docs/superpowers/specs/2026-09-25-grimoire-modernization-spec.md)
and [[21.03 Grimoire Modernization]] before changing this work. Read
[[21.01 Efficient Indexing and Project Rollout]]
for the index and adoption design. Read [[21.02 Shared MCP Runtime]] before
changing service behavior. Read [[31.01 Grimoire Wiki-RAG and Hermes Boundary]]
for integration limits.

Keep the project wiki portable across agent harnesses. Keep BM25 local. Use the
active checkout to verify code and configuration facts. Do not put credentials
or host-specific settings in tracked files. Do not replace the shared HTTP
registration with a spawn-per-client Codex registration. The refresh timer
rebuilds indexes; it does not upgrade agent contracts.

Search this wiki before asking the user to repeat a project decision or term.
Read the numbering reference below only when you need to allocate a note number.

## Numbering reference

This repo keeps durable project documentation in decimal-numbered Markdown files.
Use it as the record of what changed, why, and how to verify it.

The numbering system is inspired by [Johnny.Decimal](https://johnnydecimal.com/)
— a simple, sortable way to organize information where the tens digit is a
**category** (10-19, 20-29, ...) and the decimal is an **ID** within that
category (11.01, 11.02, ...).

## Numbering

The full 00-99 number space is available. Predefined categories:

- `00-09 System & Meta/` — wiki index, project conventions, agent contract
  - `01 Project Conventions/`
  - `02 Wiki Index/`
- `10-19 Conversations & Decisions/`
  - `11 Key Decisions/`
  - `12 Session Logs/`
- `20-29 Implementation & Operations/`
  - `21 Implementation Notes/`
  - `22 Workflows/`
- `30-39 Integrations & Tooling/`
  - `31 Tool Configs/`
  - `32 Integration Notes/`
- `40-49` — available for project-specific use
- `50-59` — available for project-specific use
- `60-69` — available for project-specific use
- `70-79` — available for project-specific use
- `80-89` — available for project-specific use
- `90-99 Archive/`
  - `91 Historical Scripts/`
  - historical notes and retired content

Projects can add their own categories in the unused ranges (40-89). Create a
folder with a descriptive name and start numbering from `.01`.

File names use decimal numbers:

- `11.01 Project Documentation Policy.md`
- `12.01 Session Log Index.md`
- `21.01 Initial Architecture Decisions.md`
- `22.01 Local Development Workflow.md`
- `31.01 MCP Server Configuration.md`

Use the next available number in the most relevant folder. Prefer updating an
existing note when the topic already exists.

## Note rule


The coordinator ensures that each meaningful project change has a note. An
agent that works alone or a coordinator updates the note. A worker returns
draft wiki changes unless assigned a specific note. Include what changed, why,
how to verify it, and rollback steps when relevant. The final response must
name the changed wiki files or say why no note was needed.
