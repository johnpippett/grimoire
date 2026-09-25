import hashlib
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/setup-projects.py'
REFRESH = Path(__file__).resolve().parents[1] / 'scripts/refresh-wiki-rag.sh'
SPEC = importlib.util.spec_from_file_location('setup_projects', SCRIPT)
SETUP_PROJECTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETUP_PROJECTS)

LEGACY_GRIMOIRE_GATE = '''## Grimoire Gate

Agents must maintain the project wiki in `wiki/` using the decimal numbering
system described in `wiki/README.md`.

Before editing:

- Inspect `wiki/` for relevant project context.
- Reuse or update existing notes when the topic already exists.

During meaningful work:

- Create or update a decimal-numbered markdown note for code, config, workflow,
  architecture, policy, dependency, integration, deployment, or debugging
  changes.
- Record what changed, why it changed, how to verify it, and rollback notes
  when rollback is relevant.
- Keep project-specific notes inside this repo's `wiki/`.

Before final response:

- Report which `wiki/` file was created or updated.
- If no wiki note was needed, explicitly say why.

Trivial read-only inspection, small formatting-only edits, and direct answers
that do not change project state may skip a wiki update, but the final response
must say that no project documentation changed.
'''

LEGACY_SETUP_GATE = '''## Grimoire Gate

Read [wiki/README.md](wiki/README.md) and relevant existing notes before editing.
After meaningful changes, update a decimal-numbered wiki note covering what,
why, verification, and rollback when relevant; append the session log index.
Report the wiki files changed, or explain why no documentation changed.
'''

PREVIOUS_GENERATED_GATE_BODY = '''At task start, read `wiki/README.md` and related notes.
Search the wiki before asking the user to repeat a decision or explain a project term.
Repeat this orientation after a topic change or loss of needed context.
Do not repeat this orientation on every turn.

If `wiki/README.md` is missing, copy `wiki-template/` or use Grimoire's `setup.sh`.
If neither is available, create the README and session-log index before work.
Put the project summary and local constraints in the README.

Use file tools when MCP search is unavailable.
MCP search covers registered project indexes. Results can be old or from another checkout.
Read the matching file in the active checkout before you use it for current facts.
Fetch incomplete passages with `read_wiki_passage`. Continue from each returned offset until the passage is complete.

Coordinators give workers task limits, related wiki notes, and source paths.
Workers return documentation findings.
The coordinator owns final wiki edits and the session-log link unless it assigns a note to a worker.

After meaningful work, update a topic note for each change to project knowledge.
Add one short link to the session log.
If no project knowledge changed, skip a wiki update and say why in the final response.'''

ROOT_PRECORRECTION_GATE_BODY = '''- At the start of a task, read `wiki/README.md` and the notes for its topic.
  Search the wiki before you ask the user to repeat a decision or explain a
  project term.
- A continuing agent repeats this orientation after a topic change or when it
  has lost the context needed for the task. It does not repeat it on every turn.
- Use ordinary file tools to search and read `wiki/` when MCP search is not
  available. MCP search covers registered project indexes. It can return old
  content or content from another checkout. Read the matching file in the
  active checkout before you use it to describe current checkout facts.
- If an MCP result marks a passage as incomplete, call `read_wiki_passage` with
  its project, generation, and chunk ID. Continue from each returned offset
  until the passage is complete. If its generation is stale, query again for a
  current reference. If passage retrieval is not available, read the source file
  with ordinary file tools. Do not use an incomplete excerpt as evidence.
- A coordinating agent gives each worker the task limits, relevant wiki
  context, and source paths. Workers read more notes when needed and return
  findings and documentation changes. The coordinator assigns note numbers,
  updates the session log, and owns final wiki edits unless it assigns a
  specific note to a worker.
- After meaningful work, update the note for changed behavior, configuration,
  decisions, user corrections, or known failures. Record what changed, why,
  how to verify it, and rollback steps when relevant. Add one short link to the
  session log. Use the numbering reference in `wiki/README.md` when you create
  a note.
- If no project knowledge changed, do not add a note. Say why in your final
  response.
- In your final response, state the work, verification, and wiki files changed,
  or explain why no wiki update was needed.

If `wiki/README.md` does not exist, copy the project's `wiki-template/` or use
Grimoire's `setup.sh`. If neither is available, create `wiki/README.md` and
`wiki/10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md`
before you start project work. Put the project summary and local constraints in
`wiki/README.md`.'''

LEGACY_BOOTSTRAP_SECTION = '''## Bootstrap (first time only)

If `wiki/` does not exist in this project root, bootstrap it now:

1. Copy the wiki template into place:
   - If `wiki-template/` exists here: `cp -r wiki-template wiki`
   - If this is a fresh project with no template, create the structure manually:
     ```
     wiki/
     ├── README.md                    (copy numbering scheme from wiki-template/README.md)
     ├── 00-09 System & Meta/
     │   ├── 01 Project Conventions/
     │   └── 02 Wiki Index/
     ├── 10-19 Conversations & Decisions/
     │   ├── 11 Key Decisions/
     │   └── 12 Session Logs/
     │       └── 12.01 Session Log Index.md
     ├── 20-29 Implementation & Operations/
     │   ├── 21 Implementation Notes/
     │   └── 22 Workflows/
     ├── 30-39 Integrations & Tooling/
     │   ├── 31 Tool Configs/
     │   └── 32 Integration Notes/
     ├── 40-89 ···  (project-specific categories — add folders as needed)
     └── 90-99 Archive/
         └── 91 Historical Scripts/
     ```
2. Confirm `wiki/README.md` and `wiki/10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md` exist.
3. Ask the user: "What does this project do?" and update the **Scope** section below with a one-line description.
4. Report: "Grimoire wiki bootstrapped at `wiki/`."

If `wiki/` already exists, skip bootstrap and proceed to **Pre-Work Checklist**.'''

LEGACY_PREWORK_SECTION = '''## Pre-Work Checklist

Before making any changes:

1. Read `AGENTS.md`, the project `README.md`, and `wiki/README.md`.
2. Scan `wiki/` for notes relevant to the task — especially in the topic's
   folder (Key Decisions, Implementation Notes, Workflows, etc.).
3. Check current state: git branch/status when available, important config
   files, and existing wiki notes.
4. If you are unsure about project conventions or architecture, ask the user
   before editing.'''

LEGACY_UPDATE_SECTION = '''## Wiki Update Workflow

After meaningful changes (code, config, workflow, architecture, deployment,
integration, debugging, or policy):

1. **Inspect** `wiki/README.md` for the numbering scheme and scan the relevant
   topic folder for existing notes. The full 00-99 number space is available;
   these categories are predefined:
   - `00-09 System & Meta/01 Project Conventions/`
   - `00-09 System & Meta/02 Wiki Index/`
   - `10-19 Conversations & Decisions/11 Key Decisions/`
   - `10-19 Conversations & Decisions/12 Session Logs/`
   - `20-29 Implementation & Operations/21 Implementation Notes/`
   - `20-29 Implementation & Operations/22 Workflows/`
   - `30-39 Integrations & Tooling/31 Tool Configs/`
   - `30-39 Integrations & Tooling/32 Integration Notes/`
   - `90-99 Archive/91 Historical Scripts/`
   - `40-89` — available for project-specific categories; create a folder
     and start numbering from `.01` when needed.

2. **Update or create** a decimal-numbered note:
   - If a note already covers the topic, **update it in place** (append to it,
     add a dated section).
   - Otherwise, create the **next decimal number** in the most relevant folder
     (e.g. if `21.01.md` and `21.02.md` exist, create `21.03 New Topic.md`).

3. **Keep the note short.** Cover:
   - What changed
   - Why it changed
   - How to verify it
   - Rollback notes (when relevant)

4. **Update the session log index.** Append a line to
   `wiki/10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md`:
   ```
   - YYYY-MM-DD (short description): What happened. [[##.## Note Name]]
   ```

5. **Report** in your final response which wiki file was created or updated.
   If no note was needed, say why (e.g. "read-only inspection — no project
   documentation changed").'''

LEGACY_SKIP_SECTION = '''## Skipping a Wiki Update

Skip for:
- Read-only inspection or Q&A about the project
- Formatting-only edits that don't change behavior
- Trivial typo fixes with no architectural impact

Even when skipping, state that no project documentation changed.'''

LEGACY_FULL_CONTRACT = (
    '# Grimoire — Agent Project Library\n\n'
    'Any coding agent working in this project must follow this file.\n\n'
    '---\n\n'
    + LEGACY_BOOTSTRAP_SECTION + '\n\n---\n\n'
    + '## Default Behavior\n\nBe concise.\nRead before editing.\nNever print secrets.\n\n---\n\n'
    + '## Scope\n\n<!-- Customize this section for your project -->\n\nTracks local application work.\n\n---\n\n'
    + LEGACY_GRIMOIRE_GATE + '\n\n---\n\n'
    + LEGACY_PREWORK_SECTION + '\n\n---\n\n'
    + LEGACY_UPDATE_SECTION + '\n\n---\n\n'
    + LEGACY_SKIP_SECTION + '\n\n'
    + '## Local Deployment Rule\n\nNever restart the local service during work.\n'
)


class SetupProjectsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'app'
        self.project.mkdir()

    def run_setup(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), '--projects-root', str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def snapshot(self):
        return {str(p.relative_to(self.project)): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}

    def test_dry_run_writes_nothing(self):
        self.run_setup()
        self.assertEqual(self.snapshot(), {})

    def test_apply_preserves_existing_files_and_is_idempotent(self):
        original = b'# Rules\r\nNever change my instructions.\r\n'
        (self.project / 'AGENTS.md').write_bytes(original)
        wiki = self.project / 'wiki'
        wiki.mkdir()
        (wiki / 'README.md').write_text('Existing wiki\n')
        self.run_setup('--apply')
        self.assertTrue((self.project / 'AGENTS.md').read_bytes().startswith(original))
        self.assertEqual((wiki / 'README.md').read_text(), 'Existing wiki\n')
        self.assertEqual(len(list(wiki.rglob('*Grimoire Adoption.md'))), 1)
        first = self.snapshot()
        self.run_setup('--apply')
        self.assertEqual(first, self.snapshot())

    def test_existing_gate_preserved_and_scope_mapping_used(self):
        original = '# Grimoire Gate\nMaintain wiki/README.md\n'
        (self.project / 'AGENTS.md').write_text(original)
        other = self.root / 'other'
        other.mkdir()
        mapping = self.root / 'scopes.json'
        mapping.write_text(json.dumps({'other': 'Tracks local tasks.'}))
        self.run_setup('--apply', '--scopes-json', str(mapping))
        self.assertEqual((self.project / 'AGENTS.md').read_text(), original)
        self.assertIn('Tracks local tasks.', (other / 'AGENTS.md').read_text())
        self.assertNotIn('canonical home', (other / 'AGENTS.md').read_text())

    def test_new_contract_scope_is_replaced_before_the_next_heading(self):
        mapping = self.root / 'scope.json'
        mapping.write_text(json.dumps({'app': 'Tracks local app tasks.'}))

        self.run_setup('--apply', '--scopes-json', str(mapping))

        contract = (self.project / 'AGENTS.md').read_text()
        self.assertIn('Tracks local app tasks.', contract)
        self.assertNotIn('This project contains the Grimoire agent project library', contract)
        self.assertIn('## Required wiki workflow', contract)

    def test_new_wiki_summary_uses_scope_only_when_template_readme_is_created(self):
        mapping = self.root / 'scope.json'
        mapping.write_text(json.dumps({'app': 'Tracks local application tasks.'}))

        output = self.run_setup('--apply', '--scopes-json', str(mapping))

        readme = (self.project / 'wiki/README.md').read_text()
        summary = readme.split('## Project summary\n', 1)[1].split('\n## Terms', 1)[0].strip()
        self.assertEqual(summary, 'Tracks local application tasks.')
        self.assertNotIn('Write one sentence that says what this project does.', readme)

        evidence_path = os.environ.get('GRIMOIRE_SUMMARY_EVIDENCE')
        if evidence_path:
            Path(evidence_path).write_text(json.dumps({
                'setup': 'Temporary direct-child project with a supplied one-line scope and a missing wiki README.',
                'steps': ['apply setup with --scopes-json', 'read the new wiki/README.md Project summary section'],
                'stdout': output,
                'summary': summary,
                'placeholder_removed': 'Write one sentence that says what this project does.' not in readme,
                'rerun': 'GRIMOIRE_SUMMARY_EVIDENCE=/tmp/grimoire-summary-e2e.json python tests/test_setup_projects.py SetupProjectsTests.test_new_wiki_summary_uses_scope_only_when_template_readme_is_created',
            }, indent=2) + '\n')

    def test_scope_substitution_stops_at_next_heading_without_a_separator(self):
        contract = (
            '# Project instructions\n\n'
            '## Scope\nOld project scope.\n\n'
            '## Required wiki workflow\nKeep the new workflow.\n'
        )

        result = SETUP_PROJECTS.substitute_scope(contract, 'New project scope.')

        self.assertEqual(result, (
            '# Project instructions\n\n'
            '## Scope\nNew project scope.\n\n'
            '## Required wiki workflow\nKeep the new workflow.\n'
        ))

    def test_existing_jd_documentation_gate_is_preserved_exactly(self):
        original = b'# Project Rules\r\n\r\n## JD Wiki Documentation Gate\r\nMaintain wiki/README.md before and after changes.\r\n'
        (self.project / 'AGENTS.md').write_bytes(original)
        self.run_setup('--apply')
        self.assertEqual((self.project / 'AGENTS.md').read_bytes(), original)

    def test_upgrade_previews_then_replaces_stock_gate_with_reversible_idempotent_change(self):
        prefix = '# Application instructions\r\n\r\nKeep the local deploy rule.\r\n\r\n'
        suffix = '\r\n---\r\n## Local rules\r\nNever restart the service during work.\r\n'
        original = prefix.encode() + LEGACY_GRIMOIRE_GATE.replace('\n', '\r\n').encode() + suffix.encode()
        agents = self.project / 'AGENTS.md'
        backup = self.project / 'AGENTS.md.grimoire-backup'
        agents.write_bytes(original)

        preview = subprocess.run(
            [sys.executable, str(SCRIPT), '--projects-root', str(self.root), '--upgrade'],
            capture_output=True, text=True,
        )
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('PREVIEW app', preview.stdout)
        self.assertIn('--- app/AGENTS.md (before)', preview.stdout)
        self.assertIn('+++ app/AGENTS.md (after)', preview.stdout)
        self.assertIn('-Agents must maintain the project wiki', preview.stdout)
        self.assertIn('+Before standalone work, a standalone agent reads', preview.stdout)
        self.assertEqual(agents.read_bytes(), original)
        self.assertFalse(backup.exists())

        first_apply = self.run_setup('--upgrade', '--apply')
        upgraded = agents.read_bytes()
        self.assertIn('APPLY app', first_apply)
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertTrue(upgraded.startswith(prefix.encode()))
        self.assertIn(b'## Required wiki workflow\r\n', upgraded)
        self.assertIn(b'Keep the local deploy rule.', upgraded)
        self.assertIn(b'Never restart the service during work.', upgraded)
        for required in (
            b'before standalone work, a standalone agent reads `wiki/readme.md` and task notes',
            b'before assigning work, a coordinator reads `wiki/readme.md` and the notes for the task topic',
            b'search the wiki before asking the user',
            b'add a short session-log link',
            b'coordinator owns final wiki edits',
            b'if no project knowledge changed',
            b'a delegated worker may rely on sufficient wiki context and source paths',
            b'a continuing worker uses fresh, sufficient wiki context and source paths',
            b'it edits a wiki note only when the coordinator assigns that note',
            b'before completion, a standalone agent or coordinator updates notes',
            b'a worker returns findings and draft wiki changes',
            b'for standalone work, or before assigning work to workers',
            b'if an mcp result marks a passage as incomplete',
            b'if its generation is stale, query again for a current reference',
            b'if passage retrieval is not available, read the source file with ordinary file tools',
            b'do not use an incomplete excerpt as evidence',
        ):
            self.assertIn(required, upgraded.lower())

        first_snapshot = self.snapshot()
        repeated_apply = self.run_setup('--upgrade', '--apply')
        self.assertIn('UP-TO-DATE app', repeated_apply)
        self.assertEqual(first_snapshot, self.snapshot())

        evidence_path = os.environ.get('GRIMOIRE_UPGRADE_EVIDENCE')
        if evidence_path:
            Path(evidence_path).write_text(json.dumps({
                'setup': 'Temporary direct-child project with a CRLF stock Grimoire Gate and unrelated local rules.',
                'steps': ['preview --upgrade', 'apply --upgrade --apply', 'apply the upgrade again'],
                'preview_stdout': preview.stdout,
                'first_apply_stdout': first_apply,
                'repeat_stdout': repeated_apply,
                'backup_matches_original': backup.read_bytes() == original,
                'backup_mode': oct(stat.S_IMODE(backup.stat().st_mode)),
                'custom_rules_preserved': b'Keep the local deploy rule.' in upgraded and b'Never restart the service during work.' in upgraded,
                'repeat_is_idempotent': first_snapshot == self.snapshot(),
                'rerun': 'GRIMOIRE_UPGRADE_EVIDENCE=/tmp/grimoire-upgrade-e2e.json python tests/test_setup_projects.py SetupProjectsTests.test_upgrade_previews_then_replaces_stock_gate_with_reversible_idempotent_change',
            }, indent=2) + '\n')

    def test_upgrade_preview_shows_gate_and_full_contract_diffs_without_writing(self):
        gate_agents = self.project / 'AGENTS.md'
        gate_original = LEGACY_SETUP_GATE.encode()
        gate_agents.write_bytes(gate_original)

        full_project = self.root / 'full-contract'
        full_project.mkdir()
        full_agents = full_project / 'AGENTS.md'
        full_original = LEGACY_FULL_CONTRACT.encode()
        full_agents.write_bytes(full_original)

        output = self.run_setup('--upgrade')

        self.assertIn('PREVIEW app: AGENTS.md', output)
        self.assertIn('--- app/AGENTS.md (before)', output)
        self.assertIn('+++ app/AGENTS.md (after)', output)
        self.assertIn('-Read [wiki/README.md](wiki/README.md)', output)
        self.assertIn('+Before standalone work, a standalone agent reads', output)
        self.assertIn('PREVIEW full-contract: AGENTS.md', output)
        self.assertIn('--- full-contract/AGENTS.md (before)', output)
        self.assertIn('+++ full-contract/AGENTS.md (after)', output)
        self.assertIn('-## Bootstrap (first time only)', output)
        self.assertIn('+## Required wiki workflow', output)
        self.assertNotIn('Never restart the local service during work.', output)
        self.assertEqual(gate_agents.read_bytes(), gate_original)
        self.assertEqual(full_agents.read_bytes(), full_original)
        self.assertFalse((self.project / 'AGENTS.md.grimoire-backup').exists())
        self.assertFalse((full_project / 'AGENTS.md.grimoire-backup').exists())

        evidence_path = os.environ.get('GRIMOIRE_UPGRADE_PREVIEW_EVIDENCE')
        if evidence_path:
            Path(evidence_path).write_text(json.dumps({
                'setup': 'Two disposable projects with an exact stock gate and an exact full legacy Grimoire contract.',
                'steps': ['write both stock contracts', 'run scripts/setup-projects.py --upgrade without --apply', 'compare output and files with the original bytes'],
                'preview_stdout': output,
                'gate_has_before_after_diff': '--- app/AGENTS.md (before)' in output and '+++ app/AGENTS.md (after)' in output,
                'full_contract_has_before_after_diff': '--- full-contract/AGENTS.md (before)' in output and '+++ full-contract/AGENTS.md (after)' in output,
                'both_projects_unchanged': gate_agents.read_bytes() == gate_original and full_agents.read_bytes() == full_original,
                'backups_absent': not (self.project / 'AGENTS.md.grimoire-backup').exists() and not (full_project / 'AGENTS.md.grimoire-backup').exists(),
                'unrelated_local_rule_omitted': 'Never restart the local service during work.' not in output,
                'rerun': 'GRIMOIRE_UPGRADE_PREVIEW_EVIDENCE=/tmp/grimoire-upgrade-preview-e2e.json python tests/test_setup_projects.py SetupProjectsTests.test_upgrade_preview_shows_gate_and_full_contract_diffs_without_writing',
            }, indent=2) + '\n')

    def test_upgrade_recognizes_previous_generated_gate_as_outdated_stock(self):
        agents = self.project / 'AGENTS.md'
        original = ('## Required wiki workflow\n\n' + PREVIOUS_GENERATED_GATE_BODY + '\n').encode()
        agents.write_bytes(original)

        output = self.run_setup('--upgrade', '--apply')

        upgraded = agents.read_text()
        self.assertIn('APPLY app: AGENTS.md', output)
        self.assertEqual((self.project / 'AGENTS.md.grimoire-backup').read_bytes(), original)
        self.assertIn('Before standalone work, a standalone agent reads', upgraded)
        self.assertIn('A delegated worker may rely on sufficient wiki context and source paths', upgraded)

    def test_upgrade_recognizes_pre_correction_root_gate_and_keeps_custom_scope(self):
        self.assertEqual(
            hashlib.sha256(ROOT_PRECORRECTION_GATE_BODY.encode()).hexdigest(),
            '73ed048ab546075656ed24eec66399ebe964fa2eac0acde5d7826099fa496d10',
        )
        original = (
            '# Project instructions\n\n'
            '## Scope\n\nTracks a customized local application.\n\n'
            '## Required wiki workflow\n'
            + ROOT_PRECORRECTION_GATE_BODY
            + '\n\n## Local rule\nKeep the local service stopped.\n'
        ).encode()
        agents = self.project / 'AGENTS.md'
        agents.write_bytes(original)

        output = self.run_setup('--upgrade', '--apply')

        upgraded = agents.read_text()
        self.assertIn('APPLY app: AGENTS.md', output)
        self.assertEqual((self.project / 'AGENTS.md.grimoire-backup').read_bytes(), original)
        self.assertIn('Tracks a customized local application.', upgraded)
        self.assertIn('Keep the local service stopped.', upgraded)
        self.assertIn('Before standalone work, a standalone agent reads', upgraded)

    def test_upgrade_skips_edited_pre_correction_root_gate(self):
        edited_gate = ROOT_PRECORRECTION_GATE_BODY + '\n\nKeep this extra local wiki rule.'
        original = (
            '# Project instructions\n\n'
            '## Scope\n\nTracks a customized local application.\n\n'
            '## Required wiki workflow\n'
            + edited_gate
            + '\n\n## Local rule\nKeep the local service stopped.\n'
        ).encode()
        agents = self.project / 'AGENTS.md'
        agents.write_bytes(original)

        output = self.run_setup('--upgrade', '--apply')

        self.assertIn('SKIP app', output)
        self.assertIn('ambiguous', output.lower())
        self.assertEqual(agents.read_bytes(), original)
        self.assertFalse((self.project / 'AGENTS.md.grimoire-backup').exists())

    def test_upgrade_refuses_to_replace_agents_changed_after_planning(self):
        agents = self.project / 'AGENTS.md'
        original = LEGACY_SETUP_GATE.encode()
        changed = original + b'\n## User edit after preview\nKeep this edit.\n'
        agents.write_bytes(original)
        plan = SETUP_PROJECTS.plan_upgrade(self.project)
        self.assertEqual(plan['status'], 'UPGRADE')

        agents.write_bytes(changed)

        with self.assertRaisesRegex(ValueError, 'changed after planning'):
            SETUP_PROJECTS.apply_upgrade(plan)

        self.assertEqual(agents.read_bytes(), changed)
        self.assertFalse((self.project / 'AGENTS.md.grimoire-backup').exists())

    def test_upgrade_backup_stays_owner_readable_for_group_read_only_source_mode(self):
        agents = self.project / 'AGENTS.md'
        agents.write_bytes(LEGACY_SETUP_GATE.encode())
        plan = SETUP_PROJECTS.plan_upgrade(self.project)
        self.assertEqual(plan['status'], 'UPGRADE')

        # Simulate an AGENTS.md source whose only read bit is for its group.
        with mock.patch.object(SETUP_PROJECTS.stat, 'S_IMODE', return_value=0o040):
            SETUP_PROJECTS.apply_upgrade(plan)

        backup = self.project / 'AGENTS.md.grimoire-backup'
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)

    def test_upgrade_skips_edited_gate_without_writing_or_backup(self):
        original = b'# Rules\n\n## Grimoire Gate\n\nKeep this custom gate text.\n'
        agents = self.project / 'AGENTS.md'
        agents.write_bytes(original)

        output = self.run_setup('--upgrade', '--apply')

        self.assertIn('SKIP app', output)
        self.assertIn('ambiguous', output.lower())
        self.assertEqual(agents.read_bytes(), original)
        self.assertFalse((self.project / 'AGENTS.md.grimoire-backup').exists())

    def test_upgrade_recognizes_previous_stock_setup_gate(self):
        agents = self.project / 'AGENTS.md'
        original = LEGACY_SETUP_GATE.encode()
        agents.write_bytes(original)

        self.run_setup('--upgrade', '--apply')

        self.assertEqual((self.project / 'AGENTS.md.grimoire-backup').read_bytes(), original)
        self.assertIn(b'## Required wiki workflow', agents.read_bytes())

    def test_scheduled_refresh_dry_run_does_not_request_contract_upgrade(self):
        environment = os.environ.copy()
        environment.update({
            'GRIMOIRE_WIKI_RAG_CONFIG': str(self.root / 'missing-config.env'),
            'WIKI_RAG_PROJECTS_ROOT': str(self.root),
            'WIKI_RAG_HOME': str(self.root / 'index'),
            'WIKI_RAG_AUTO_SETUP': '1',
            'GRIMOIRE_WIKI_RAG_DRY_RUN': '1',
            'UV_BIN': '/bin/true',
        })
        result = subprocess.run(['bash', str(REFRESH)], capture_output=True, text=True, env=environment)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('setup-projects.py', result.stdout)
        self.assertIn('--apply', result.stdout)
        self.assertNotIn('--upgrade', result.stdout)
        self.assertEqual(self.snapshot(), {})

        evidence_path = os.environ.get('GRIMOIRE_REFRESH_EVIDENCE')
        if evidence_path:
            Path(evidence_path).write_text(json.dumps({
                'setup': 'Dry-run scheduled refresh with automatic setup enabled and a temporary projects root.',
                'steps': ['run scripts/refresh-wiki-rag.sh with dry-run and auto-setup environment values', 'inspect the printed setup command'],
                'stdout': result.stdout,
                'setup_command_excludes_upgrade': '--upgrade' not in result.stdout,
                'project_files_unchanged': not self.snapshot(),
                'rerun': 'GRIMOIRE_REFRESH_EVIDENCE=/tmp/grimoire-refresh-e2e.json python tests/test_setup_projects.py SetupProjectsTests.test_scheduled_refresh_dry_run_does_not_request_contract_upgrade',
            }, indent=2) + '\n')

    def test_upgrade_replaces_all_stock_sections_and_preserves_custom_scope_and_rules(self):
        original = LEGACY_FULL_CONTRACT.encode()
        agents = self.project / 'AGENTS.md'
        backup = self.project / 'AGENTS.md.grimoire-backup'
        agents.write_bytes(original)

        output = self.run_setup('--upgrade', '--apply')

        upgraded = agents.read_text()
        self.assertIn('APPLY app', output)
        self.assertEqual(backup.read_bytes(), original)
        self.assertIn('Tracks local application work.', upgraded)
        self.assertIn('Never print secrets.', upgraded)
        self.assertIn('Never restart the local service during work.', upgraded)
        self.assertIn('## Required wiki workflow', upgraded)
        self.assertNotIn('## Bootstrap (first time only)', upgraded)
        self.assertNotIn('## Grimoire Gate', upgraded)
        self.assertNotIn('## Pre-Work Checklist', upgraded)
        self.assertNotIn('## Wiki Update Workflow', upgraded)
        self.assertNotIn('## Skipping a Wiki Update', upgraded)
        self.assertNotIn('What does this project do?', upgraded)

        evidence_path = os.environ.get('GRIMOIRE_FULL_UPGRADE_EVIDENCE')
        if evidence_path:
            Path(evidence_path).write_text(json.dumps({
                'setup': 'Disposable project with exact stock legacy Grimoire sections, a custom Scope, custom safety text, and a local deployment rule.',
                'steps': ['write the legacy contract to AGENTS.md', 'apply --upgrade --apply'],
                'stdout': output,
                'backup_matches_original': backup.read_bytes() == original,
                'custom_instructions_preserved': all(token in upgraded for token in (
                    'Tracks local application work.', 'Never print secrets.', 'Never restart the local service during work.',
                )),
                'legacy_workflow_removed': all(token not in upgraded for token in (
                    '## Bootstrap (first time only)', '## Pre-Work Checklist', '## Wiki Update Workflow',
                )),
                'rerun': 'GRIMOIRE_FULL_UPGRADE_EVIDENCE=/tmp/grimoire-full-upgrade-e2e.json python tests/test_setup_projects.py SetupProjectsTests.test_upgrade_replaces_all_stock_sections_and_preserves_custom_scope_and_rules',
            }, indent=2) + '\n')

    def test_skips_hidden_generated_and_symlink_paths(self):
        for name in ('.hidden', 'node_modules', 'dist', 'build'):
            (self.root / name).mkdir()
        (self.root / 'link').symlink_to(self.project, target_is_directory=True)
        (self.project / 'wiki').symlink_to(self.root / 'dist', target_is_directory=True)
        self.run_setup('--apply')
        self.assertFalse((self.root / 'dist' / 'README.md').exists())
        self.assertFalse((self.project / 'AGENTS.md').exists())
        for name in ('.hidden', 'node_modules', 'dist', 'build'):
            self.assertEqual(list((self.root / name).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
