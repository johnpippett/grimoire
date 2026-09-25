# Modernization validation — 2026-09-25

This report records the fresh-agent contract trial. The runtime and upgrade
tests use disposable projects and produce JSON evidence.

## Trial setup

Four disposable projects used the same runtime decision note and the same
incorrect `docs/runtime.md`. The note said that two Codex clients share one
authenticated loopback Streamable HTTP service. It also recorded that 74
duplicate stdio servers used excessive memory. The document said that Codex
uses one stdio server per client.

The old projects used `AGENTS.md` and `wiki-template/README.md` from Git
`HEAD` before modernization. The new projects used the shorter contract and
wiki template from this worktree. Each new wiki entry point named the runtime
note, the active correction, and the limit on machine changes. Each project
had its own files. No trial changed the live service or saved checkout.

All initial trials received this prompt:

> You are a fresh project agent. A worker handoff proposes moving Codex to a separate Grimoire stdio server per client to simplify setup. Decide using this project's durable knowledge. Correct docs/runtime.md if it conflicts with the recorded decision. Complete the project's documentation workflow for a meaningful change. Do not alter machine settings or access personal memory. In your final answer, cite the project source and state what you changed.

Each continued trial received this prompt:

> Continue this same task. A second worker asks whether adding a second Codex client changes the recorded recommendation. Answer from the context already gathered. Do not edit files or read personal memory. Report whether you reread any project files in this continuation, and list them if so.

## Codex CLI with Luna

The CLI used `gpt-6-luna` with maximum reasoning in four runs. It used a
temporary `CODEX_HOME` that held only an authentication link and new session
files. `--ignore-user-config` excluded user configuration. The temporary home
had no personal memory files. The first turns used `codex exec --json` with
`--skip-git-repo-check`, `--sandbox workspace-write`, and each fixture as
`--cd`. The second turns used `codex exec resume --json` with the thread ID.
The raw JSONL and fixture files are under `/tmp/grimoire-modernization-trial/`
on the test host. To repeat the trial, recreate the fixture from the setup
above and use the two prompts with a fresh temporary `CODEX_HOME`.

| Contract | Turn | Result | Input tokens | Cached input tokens | Output tokens | Elapsed | Shell commands | Wiki read commands |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Old | Initial | Corrected document, note, and session log | 155,883 | 137,216 | 3,809 | 158 s | 5 | 4 |
| New | Initial | Corrected document, note, and session log | 104,215 | 91,648 | 2,325 | 55 s | 4 | 3 |
| Old | Continued | Correct answer; no file read or edit | 24,605 | 22,272 | 415 | 14 s | 0 | 0 |
| New | Continued | Correct answer; no file read or edit | 21,726 | 19,200 | 478 | 14 s | 0 | 0 |

The first CLI run gives the initial turn's token use. The resumed run's totals
include both turns. The continued turn's figures subtract the first run from
the resumed run. Cached input tokens are part of input tokens; do not add the
columns. The raw `turn.completed` events are in the JSONL files above. The
calculation record is at
`/tmp/grimoire-review-token-accounting.json` on the test host. File creation
and last-write times supplied elapsed time with one-second precision. Both
contracts recovered the decision. The new contract used one fewer wiki read
command in the initial turn. Neither agent
reread files in the continued turn. The new initial turn used 33% fewer input
tokens in this one trial. The old agent read `wiki/README.md` twice in its
initial turn; the new agent read it once. These are observed runs, not a
latency guarantee.

## Codex app agent runner with Luna

Fresh delegated agents used Luna with maximum reasoning and no inherited turn
history. Each agent received one disposable fixture and an instruction not to
read personal memory. The runner did not expose a separate memory-off switch.
Both agents recovered the same decision, corrected the document, updated the
existing wiki note, and added a session-log link. Both continued agents gave
the correct answer without reading another file. The runner did not provide
token use or exact elapsed time. The results came from agent reports and file
readback; the CLI JSONL provides the measured comparison above.

OpenCode was present, but its credential list was empty. It could not run a
Luna trial. No configured Luna route was available in Claude Code. The two
trials therefore covered two Codex runner surfaces. They did not establish
cross-vendor behavior.

## Real MCP tests

Run these scripts with the locked Python dependencies. Each script creates
temporary projects and indexes. It writes a JSON report with setup, steps,
results, and a rerun command:

```bash
(cd grimoire-mcp && uv sync --locked)
grimoire-mcp/.venv/bin/python grimoire-mcp/tests/e2e_search.py --output /tmp/grimoire-search-e2e.json
grimoire-mcp/.venv/bin/python grimoire-mcp/tests/e2e_shared_runtime.py --output /tmp/grimoire-shared-runtime-e2e.json
```

The primary-agent search run passed six steps. The query response had exactly
8,000 characters, five returned hits, and 20 omitted hits. It recovered a
4,689-character indexed passage in two pages. A stale generation told the
client to query again. Evidence is in
`/tmp/grimoire-search-e2e-primary.json` on the test host.

The final-source rerun passed the same six steps. Its evidence is in
`/tmp/grimoire-search-e2e-final.json`.

The primary-agent shared HTTP run passed ten steps. It checked tool discovery,
authentication, loopback binding, restart, and persisted index use. Twelve
independent clients used one server PID during the concurrency step. Evidence
is in `/tmp/grimoire-shared-runtime-modernization-primary.json`. This test
used a disposable port and token. The installed user service kept PID 1138,
and its refresh timer stayed active.

The final-source rerun passed the same ten steps. Its evidence is in
`/tmp/grimoire-shared-runtime-modernization-final.json`.

## Project setup and upgrade tests

The `setup-projects.py` suite passed 19 `unittest` tests. It used disposable projects and
left the saved checkout unchanged. Its end-to-end records are at
`/tmp/grimoire-{upgrade,full-upgrade,summary,refresh,setup}-e2e.json` on the
test host. Each record gives the fixture, steps, result, and rerun command.

The upgrade preview prints a unified before/after diff for each recognized
contract. A disposable E2E test covered a stock gate and a full legacy
contract. It shows changed lines without adjacent local rules. The preview
left both project files unchanged and created no
backups. Its final-source record is at
`/tmp/grimoire-upgrade-preview-e2e-final.json` on the test host. Apply
preserved the original `AGENTS.md` bytes in a mode `0600` backup. It kept custom
rules and Scope. A second run made no change. A full stock legacy contract was upgraded as
one unit. The upgrade also recognizes previous stock generated and root gates
by exact fingerprints; it skips edited workflow text. A changed target between
preview and apply was rejected. New wiki entry points received the supplied
one-line scope. A scheduled refresh dry run
did not request a contract upgrade.

Independent review found that a group-readable-only source could create an
unreadable backup. A new regression failed before the correction and passed
after the backup mode became `0600` in all cases.

Repeat the suite from this worktree:

```bash
python -m unittest discover -s tests -v
```

The primary agent ran the combined Python suite after both search review
fixes and the backup correction. It passed 51 tests at that stage:

```bash
PYTHONPATH=grimoire-mcp/src /tmp/grimoire-search-env/bin/python -m pytest -q grimoire-mcp/tests tests
```

One regression checks that JSON-escaped provenance stays within the
8,000-character response limit and that an incomplete passage page advances.
Another interleaves a no-hit query from generation G1 with publication of G2.
It checks that the reply identifies G1. Both tests failed before their
respective fixes and passed after them.

After the worker intake and upgrade preview corrections, the combined suite
passed 62 tests and 50 subtests. The project setup and contract guidance suite
passed 30 tests. The preview E2E test passed again against the final source.
The search and shared HTTP source did not change in these corrections; their
six-step and ten-step MCP E2E results above still apply.

## Limits

The measured new contract preceded a final short project-safety paragraph in
`AGENTS.md` and the later worker-intake clarification. These runs do not
measure the effects of those edits. The trial fixtures did not use MCP, so the
search API has separate real-MCP tests. The
official ASD-STE100 Issue 9 PDF could not be fetched on this host. Its full
dictionary was not checked, and this report does not claim verified compliance.
