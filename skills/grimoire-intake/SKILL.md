---
name: grimoire-intake
description: Use when an agent works alone, coordinates workers, receives a work assignment, changes task topics or agents, or resumes after context loss.
---

# Grimoire Intake

Use this to load the project context needed for the assigned task.

## Steps

1. Find the project root and read its local agent instructions.
2. An agent that works alone reads `wiki/README.md` and the notes for the task
   topic before work. A coordinator does the same before it assigns work.
   Search the wiki before asking the user to repeat a decision or explain a term.
3. A worker may use sufficient wiki context and source paths from the
   coordinator. Read more notes only when needed.
4. If MCP search is unavailable, use file tools. For example, list files with
   `rg --files wiki` and search text with `rg -n "term" wiki`.
5. Treat MCP results as indexed search results for registered projects. They
   can be stale or come from another checkout. Read the matching file in the
   active checkout before using it as a current project fact.
6. If a result marks a passage as incomplete, call `read_wiki_passage` with its
   project, generation, and chunk ID. Continue at each returned offset until
   complete. If the generation is stale, search again for a new reference. If
   passage retrieval is unavailable, read the source file with file tools.
7. After a topic change or context loss, an agent that works alone repeats this
   initial wiki read. A coordinator does the same. A continuing worker uses new,
   sufficient wiki context and source paths from the coordinator. Read more
   notes only when needed.
8. Check the current branch, working tree, relevant configuration, and existing
   documentation before editing.
9. For delegated work, follow the task limits from the coordinator. Return
   findings and draft wiki changes. Edit a wiki note only when the coordinator
   assigns it. The coordinator assigns note numbers and updates the session log.
   It makes final wiki edits. It can assign a specific note to a worker.
10. Never print secrets. Ask before destructive Git, machine-level, or
   security-sensitive changes.

## Output

Report the work and what you verified. An agent that works alone or a
coordinator names the wiki files changed. If it makes no wiki update, it
explains why. A worker reports draft wiki changes sent to the coordinator or
the note it was assigned to edit.
