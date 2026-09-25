# Project skills

These skills help agents work on Grimoire itself. Consumer projects can use the
portable contract in `AGENTS.md` without installing these skills. The skills
add detail for harnesses that support them; they do not replace the contract.

- Use `grimoire-intake` when an agent works alone or a coordinator assigns
  work. After a topic change or context loss, an agent that works alone repeats
  the initial wiki read. A coordinator does the same. A worker may use new,
  sufficient wiki context and source paths from the coordinator. Read more
  notes only when needed.
- Workers return findings and draft wiki changes unless assigned a note. The
  coordinator assigns note numbers, updates the session log, and makes final
  wiki edits. It can assign a specific note to a worker.
- Use `grimoire-update` when work changes project behavior or recorded
  knowledge.

Add a skill only when it describes a repeatable project task.
