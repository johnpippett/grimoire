# Project instructions

## Scope

This project contains the Grimoire agent project library, its portable wiki
contract, and the local `grimoire-mcp` search service.

---

## Project safety

- Read relevant files before editing. Check the Git status and important
  configuration first.
- Never print secrets.
- Ask before destructive Git, machine-level, or security-sensitive changes.
- Do not commit, push, reset, release, or rewrite history unless asked.

## Required wiki workflow

- An agent that works alone reads `wiki/README.md` and the notes for the task
  topic before work. A coordinator does the same before it assigns work.
  Search the wiki before asking the user to repeat a decision or explain a term.
- A worker may use sufficient wiki context and source paths from the
  coordinator. It reads more notes only when needed.
- After a topic change or context loss, an agent that works alone repeats this
  initial wiki read. A coordinator does the same. A continuing worker uses new,
  sufficient wiki context and source paths from the coordinator. It reads more
  notes only when needed.
- Use ordinary file tools to search and read `wiki/` when MCP search is not
  available. MCP search covers registered project indexes. It can return old
  content or content from another checkout. Read the matching file in the
  active checkout before you use it to describe current checkout facts.
- If an MCP result marks a passage as incomplete, call `read_wiki_passage` with
  its project, generation, and chunk ID. Continue from each returned offset
  until the passage is complete. If its generation is stale, query again for a
  current reference. If passage retrieval is not available, read the source file
  with ordinary file tools. Do not use an incomplete excerpt as evidence.
- The coordinator gives each worker the task limits, relevant wiki context,
  and source paths. A worker returns findings and draft wiki changes. It edits
  a wiki note only when the coordinator assigns that note.
- After meaningful work, an agent that works alone or a coordinator updates
  the note. Record changed behavior, configuration, decisions, corrections,
  and known failures. State what changed, why, and how to verify it. Add
  rollback steps when relevant. Add one short link to the session log. Use the
  numbering reference in `wiki/README.md` when creating a note.
- The coordinator assigns note numbers, updates the session log, and makes the
  final wiki edits. It can assign a specific note to a worker.
- If no project knowledge changed, do not add a note. Say why in your final
  response.
- In the final response, state the work and verification. An agent that works
  alone or a coordinator names the wiki files changed. If it makes no wiki
  update, it explains why. A worker reports draft wiki changes sent to the
  coordinator or the note it was assigned to edit.

If `wiki/README.md` does not exist, an agent that works alone or a coordinator
copies `wiki-template/` or runs Grimoire's `setup.sh`. If neither is available,
create `wiki/README.md` and `wiki/10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md`.
Do this before work. Put the project summary and local constraints in
`wiki/README.md`.

## Public technical writing

For English technical text prepared for public use or external submission,
follow ASD-STE100 Issue 9 (2025-01-15). Use the official [rules and
dictionary](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf).
Use approved words with their approved meanings and parts of speech. Use one
term for each technical concept. Prefer active voice, clear steps, and short
sentences. Keep code, commands, identifiers, paths, URLs, logs, and quotations
unchanged. Review the text against the standard before delivery. Do not claim
verified compliance without a complete review. This writing rule does not
authorize publication or submission.
