---
name: grimoire-update
description: Use when project work changes behavior, configuration, workflow, architecture, deployment, integration, policy, or recorded project knowledge.
---

# Grimoire Update

Use this workflow to record project knowledge. The coordinator assigns note
numbers, updates the session log, and makes final wiki edits. It can assign a
specific note to a worker.

## Workflow

1. An agent that works alone reads `wiki/README.md` and the notes for the task
   topic before work. A coordinator does the same before it assigns work.
   A worker may use sufficient wiki context and source paths from the
   coordinator. Read more notes only when needed. If MCP search is unavailable,
   search and read files with ordinary file tools.
2. Treat MCP search as an index of registered projects. Read the matching file
   in the active checkout before you use it as a current project fact.
3. If an MCP result marks a passage as incomplete, call `read_wiki_passage` with
   its project, generation, and chunk ID. Continue at each returned offset until
   the passage is complete. If its generation is stale, query again for a new
   reference. If passage retrieval is unavailable, read the source file with
   file tools. Do not rely on an incomplete excerpt.
4. An agent that works alone or a coordinator updates the existing topic note
   or creates the next note. A worker returns draft wiki changes. It edits a
   note only when the coordinator assigns it.
5. Record what changed, why, how to verify it, and rollback steps when relevant.
   Include affected behavior, configuration, decisions, user corrections, or
   known failures.
6. After meaningful work, agents that work alone and coordinators add one
   short link to the session log. A worker returns findings and a proposed log
   link to the coordinator.
7. After a topic change or context loss, an agent that works alone repeats this
   initial wiki read. A coordinator does the same. A continuing worker uses new,
   sufficient wiki context and source paths from the coordinator. Read more
   notes only when needed.
8. If no recorded knowledge changed, do not add a note. State why in the final
   response.

## Final response

Report what you verified. An agent that works alone or a coordinator names the
wiki files changed. If it makes no wiki update, it explains why. A worker
reports draft wiki changes sent to the coordinator or the note it was assigned
to edit.
