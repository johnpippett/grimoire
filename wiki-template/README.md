# Project Wiki

This wiki stores project facts, decisions, and work notes beside the code.

## Project summary

<!-- Write one sentence that says what this project does. -->

## Terms

<!-- Define local terms and abbreviations. Link to a note for long definitions. -->

## Current work

<!-- Link to notes about active work. Remove this section when it is empty. -->

## Constraints

<!-- Record limits that affect project work. Link to the source note. -->

## Topic notes

<!-- Link to the most useful notes for each topic. -->

## Agent orientation

An agent that works alone reads `wiki/README.md` and the notes for the task
topic before work. A coordinator does the same before it assigns work.
Search the wiki before asking the user to repeat a decision or explain a term.
Use file tools to search the wiki when MCP search is not available.

A delegated worker may use sufficient wiki context and source paths from the
coordinator. Read more notes only when needed. After a topic change or context
loss, an agent that works alone repeats this initial wiki read. A coordinator
does the same. A continuing worker uses new, sufficient wiki context and source
paths from the coordinator. Read more notes only when needed.

MCP search covers registered indexes and can be out of date. Read files in the
active checkout before using indexed results as current project facts. If a
result marks a passage as incomplete, use `read_wiki_passage` with its project,
generation, and chunk ID. Continue until the passage is complete. If the
reference is stale, search again. If passage retrieval is not available, read
the source file with file tools.

After meaningful work, agents that work alone and coordinators update a topic
note. The note records changed behavior, configuration, decisions, corrections,
and known failures. State what changed, why, and how to verify it. Add rollback
steps when relevant. Add one short entry to the session log at
[`12.01 Session Log Index`](10-19%20Conversations%20%26%20Decisions/12%20Session%20Logs/12.01%20Session%20Log%20Index.md).
A worker returns findings and draft wiki changes. It edits a wiki note only
when the coordinator assigns it. The coordinator assigns note numbers, updates
the session log, and makes final wiki edits. It can assign a specific note.
If no project knowledge changed, do not add a note. State why in your final
response. Read the numbering reference below only when you create a note.

## Numbering reference

The full `00`-`99` number space is available. The tens digit names a category;
the decimal is an ID in that category. This system is inspired by
[Johnny.Decimal](https://johnnydecimal.com/).

Common categories:

- `00-09 System & Meta/` — project conventions and wiki indexes
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
- `40-89` — project-specific categories
- `90-99 Archive/` — old notes and retired content
  - `91 Historical Scripts/`

Create folders for project-specific categories in the `40-89` range. Start
numbering at `.01` in each folder. Use the next available number in the folder
that best fits the topic. Update an existing note when it covers the same topic.

File name examples:

- `11.01 Project Decisions.md`
- `12.01 Session Log Index.md`
- `21.01 Architecture Notes.md`
- `22.01 Local Workflow.md`
- `31.01 Tool Configuration.md`

## Note rule

The coordinator ensures that each meaningful project change has a note. An
agent that works alone or a coordinator updates the note. A worker returns
draft wiki changes unless assigned a specific note. Include what changed, why,
how to verify it, and rollback steps when relevant. The final response must
name the changed wiki files or say why no note was needed.
