#!/usr/bin/env python3
"""Adopt Grimoire in direct-child projects, preserving existing files.

Preview by default; pass --apply to write. No git or machine configuration changes.
"""
import argparse
from datetime import date
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / 'wiki-template'
LOG = Path('10-19 Conversations & Decisions/12 Session Logs/12.01 Session Log Index.md')
NOTES = Path('30-39 Integrations & Tooling/32 Integration Notes')
SKIP = {'node_modules', 'build', 'dist', 'target', 'vendor', 'venv', '__pycache__'}
MARKER = '<!-- grimoire-project-adoption -->'
GATE = '''\n\n## Required wiki workflow

Before standalone work, a standalone agent reads `wiki/README.md` and task notes.
Before assigning work, a coordinator reads `wiki/README.md` and the notes for the task topic.
Search the wiki before asking the user to repeat a decision or explain a term.
A delegated worker may rely on sufficient wiki context and source paths from the coordinator.
It reads more notes only when needed.
After a topic change or context loss, standalone agents and coordinators repeat the full orientation.
A continuing worker uses fresh, sufficient wiki context and source paths from the coordinator.
It reads more notes only when needed.

Use file tools when MCP search is unavailable.
MCP search covers registered project indexes. Results can be old or from another checkout.
Read the matching file in the active checkout before you use it for current facts.
If an MCP result marks a passage as incomplete, call `read_wiki_passage` with its project, generation, and chunk ID.
Continue from each returned offset until the passage is complete.
If its generation is stale, query again for a current reference.
If passage retrieval is not available, read the source file with ordinary file tools.
Do not use an incomplete excerpt as evidence.

The coordinator gives each worker task limits, relevant wiki context, and source paths.
A worker returns findings and draft wiki changes.
It edits a wiki note only when the coordinator assigns that note.

Before completion, a standalone agent or coordinator updates notes for changed behavior, configuration, decisions, corrections, or known failures.
Record what changed, why, how to verify it, and rollback steps when relevant. Add a short session-log link.
Use the numbering reference in `wiki/README.md` when creating a note.
The coordinator owns final wiki edits unless it assigns a note to a worker. It assigns note numbers and updates the session log.
If no project knowledge changed, skip the wiki update and say why in the final response.
In the final response, state the work and verification. Name wiki files changed, or explain why no wiki update was needed.
A worker reports draft changes returned to the coordinator or the note it was assigned to edit.

For standalone work, or before assigning work to workers, if `wiki/README.md` is missing, copy `wiki-template/` or use Grimoire's `setup.sh`.
If neither is available, create the README and session-log index before project work.
Put the project summary and local constraints in the README.
'''
UPGRADE_BACKUP = Path('AGENTS.md.grimoire-backup')
UPGRADE_HEADINGS = {'Grimoire Gate', 'Required wiki workflow'}
# Exact earlier stock sections accepted for safe upgrades. These fingerprints
# cover the prior script-generated gate and the pre-correction root contract.
STOCK_REQUIRED_WORKFLOW_SHA256 = {
    'ff8b519a0066705724f507d4236688a5cbdfab57fff2fb93c4ac0aa315090839',
    '73ed048ab546075656ed24eec66399ebe964fa2eac0acde5d7826099fa496d10',
}
LEGACY_GRIMOIRE_GATE = '''Agents must maintain the project wiki in `wiki/` using the decimal numbering
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
must say that no project documentation changed.'''
LEGACY_SETUP_GATE = '''Read [wiki/README.md](wiki/README.md) and relevant existing notes before editing.
After meaningful changes, update a decimal-numbered wiki note covering what,
why, verification, and rollback when relevant; append the session log index.
Report the wiki files changed, or explain why no documentation changed.'''
LEGACY_FULL_SECTION_SHA256 = {
    'Bootstrap (first time only)': '442e822339430a0c9e6e22d8c2be9c507d6aa949cd96d2b2590c955af2719021',
    'Grimoire Gate': '2cba348098db8ee90384cd56c29c23a6d40682b82deae463f4c4e69a7f840d05',
    'Pre-Work Checklist': '94413bb42159e0d99263c82224896e418a993f5b6195c20dfd94d8a0d7bf4fae',
    'Wiki Update Workflow': 'b9c8fadd4a1f078507e01cad2e886bdb2b859788cffd7580a45bb4a8e96b7188',
    'Skipping a Wiki Update': '16bd94f2673145e6452079ecfbdab3bae6c0cc20ca825522d21ccf25bdd1a6ff',
}


def plan_project(project, scope):
    """Return relative-path/new-bytes edits without following destination symlinks."""
    wiki = project / 'wiki'
    agents = project / 'AGENTS.md'
    # Refuse the whole project before any writes if a managed path redirects.
    if wiki.is_symlink() or agents.is_symlink():
        raise ValueError('wiki or AGENTS.md is a symlink')
    if wiki.exists() and not wiki.is_dir():
        raise ValueError('wiki is not a directory')
    if wiki.exists() and any(p.is_symlink() for p in wiki.rglob('*')):
        raise ValueError('wiki contains a symlink')
    edits = {}
    for source in sorted(TEMPLATE.rglob('*')):
        if not source.is_file() or source.is_symlink():
            continue
        destination = Path('wiki') / source.relative_to(TEMPLATE)
        if not (project / destination).exists():
            content = source.read_bytes()
            if destination == Path('wiki/README.md'):
                content = content.replace(
                    b'<!-- Write one sentence that says what this project does. -->',
                    scope.encode('utf-8'),
                )
            edits[destination] = content
    if not agents.exists():
        contract = (REPO / 'AGENTS.md').read_text()
        contract = substitute_scope(contract, scope)
        edits[Path('AGENTS.md')] = contract.encode()
    else:
        original = agents.read_bytes()
        text = original.decode('utf-8')
        existing_gate = re.search(
            r'^#{1,6}\s+(?:Grimoire Gate|Required wiki workflow|(?:JD\s+)?Wiki Documentation Gate)\s*$',
            text, re.I | re.M,
        )
        if not existing_gate:
            edits[Path('AGENTS.md')] = original + GATE.encode()
    existing = list((wiki / NOTES).glob('*.md')) if (wiki / NOTES).exists() else []
    adopted = any(MARKER in p.read_text() for p in existing)
    if not adopted:
        numbers = [int(m[1]) for p in existing if (m := re.match(r'32\.(\d+)', p.name))]
        title = f'32.{max(numbers, default=0) + 1:02d} Grimoire Adoption'
        note = f'''# {title}

{MARKER}

## What and why

Enabled the Grimoire project wiki and agent entry point for durable project
context and local cross-project wiki search. Existing project files were preserved.
Project scope: {scope}

## Verify

Read `AGENTS.md` and `wiki/README.md`; confirm the session log and this note exist.
After refreshing the local Grimoire index, list projects and query this project's wiki.

## Rollback

Remove only files introduced by setup and the appended wiki workflow block, if any.
Preserve pre-existing wiki files and agent instructions. Remove this note and its
session-log entry if reverting adoption; refresh the derived search index afterward.
'''
        edits[Path('wiki') / NOTES / (title + '.md')] = note.encode()
        log_path = Path('wiki') / LOG
        previous = (project / log_path).read_bytes() if (project / log_path).exists() else edits.get(log_path, b'# Session Log Index\n')
        edits[log_path] = previous + f'\n- {date.today().isoformat()} (Grimoire adoption): Enabled project wiki and agent entry point. [[{title}]]\n'.encode()
    # Preflight all parent components, including file/directory collisions.
    for relative in edits:
        target = project / relative
        if target.exists() and not target.is_file():
            raise ValueError(f'expected file: {relative}')
        for parent in target.parents:
            if parent == project:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f'expected directory: {parent.relative_to(project)}')
    return edits


def substitute_scope(contract, scope):
    """Replace only the Scope section body, ending at its next peer heading."""
    lines = contract.splitlines(keepends=True)
    scope_index = None
    scope_level = None
    for index, line in enumerate(lines):
        match = re.fullmatch(r'(#{1,6})[ \t]+Scope[ \t]*(?:\r?\n)?', line)
        if match:
            scope_index = index
            scope_level = len(match.group(1))
            break
    if scope_index is None:
        raise ValueError('root AGENTS.md has no Scope section')

    end = len(lines)
    for index in range(scope_index + 1, len(lines)):
        match = re.match(r'^(#{1,6})[ \t]+', lines[index])
        if match and len(match.group(1)) <= scope_level:
            end = index
            break

    newline = '\r\n' if any('\r\n' in line for line in lines) else '\n'
    return ''.join(lines[:scope_index + 1]) + scope + newline + newline + ''.join(lines[end:])


def _line_text(line):
    return line.rstrip('\r\n')


def _normalize_section(text):
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def _markdown_sections(lines):
    """Return ATX sections and ignore heading-like lines inside code fences."""
    headings = []
    fence = None
    for index, line in enumerate(lines):
        plain = _line_text(line)
        marker = re.match(r'^\s*(`{3,}|~{3,})', plain)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            continue
        match = re.fullmatch(r'(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*', plain)
        if match:
            headings.append((index, len(match.group(1)), match.group(2)))

    sections = []
    for position, (start, level, title) in enumerate(headings):
        end = len(lines)
        for next_start, next_level, _ in headings[position + 1:]:
            if next_level <= level:
                end = next_start
                break
        body, separator = _section_body_and_separator(lines[start:end])
        sections.append({
            'start': start,
            'end': end,
            'level': level,
            'title': title,
            'body': body,
            'separator': separator,
        })
    return sections


def _section_body_and_separator(section):
    """Return normalized body text and its final horizontal-rule separator."""
    delimiter = None
    for index in range(len(section) - 1, 0, -1):
        if _line_text(section[index]).strip() == '---' and all(
            not _line_text(line).strip() for line in section[index + 1:]
        ):
            delimiter = index
            break
    separator_start = delimiter
    if separator_start is not None:
        while separator_start > 1 and not _line_text(section[separator_start - 1]).strip():
            separator_start -= 1
        body_lines = section[1:separator_start]
        separator = ''.join(section[separator_start:])
    else:
        body_lines = section[1:]
        separator = ''
    return _normalize_section(''.join(body_lines)), separator


def _canonical_gate_section(level, separator, newline):
    gate = GATE.strip('\n').split('\n', 1)[1]
    section = f'{"#" * level} Required wiki workflow{newline}' + gate.replace('\n', newline)
    if separator:
        return section + newline + separator
    return section + newline


def _make_upgrade_plan(project, original, updated):
    backup = project / UPGRADE_BACKUP
    if backup.is_symlink():
        return {'status': 'SKIP', 'reason': 'rollback backup path is a symlink'}
    if backup.exists() and backup.read_bytes() != original:
        return {'status': 'SKIP', 'reason': 'rollback backup path already contains different bytes'}
    return {
        'status': 'UPGRADE',
        'original': original,
        'updated': updated.encode('utf-8'),
        'backup': backup,
        'backup_exists': backup.exists(),
        'target': project / 'AGENTS.md',
    }


def _replace_sections(lines, replacements):
    pieces = []
    cursor = 0
    for section, content in sorted(replacements, key=lambda item: item[0]['start']):
        pieces.append(''.join(lines[cursor:section['start']]))
        if content is not None:
            pieces.append(content)
        cursor = section['end']
    pieces.append(''.join(lines[cursor:]))
    return ''.join(pieces)


def plan_upgrade(project):
    """Prepare an upgrade for exact, recognized Grimoire contract sections."""
    agents = project / 'AGENTS.md'
    if agents.is_symlink():
        return {'status': 'SKIP', 'reason': 'AGENTS.md is a symlink'}
    if not agents.is_file():
        return {'status': 'SKIP', 'reason': 'AGENTS.md is missing'}

    original = agents.read_bytes()
    text = original.decode('utf-8')
    lines = text.splitlines(keepends=True)
    sections = _markdown_sections(lines)
    grouped = {}
    for section in sections:
        grouped.setdefault(section['title'], []).append(section)

    legacy_names = set(LEGACY_FULL_SECTION_SHA256)
    full_contract_present = any(name in grouped for name in legacy_names - {'Grimoire Gate'})
    current_sections = grouped.get('Required wiki workflow', [])
    if full_contract_present:
        if current_sections:
            return {'status': 'SKIP', 'reason': 'ambiguous file mixes old and new Grimoire sections'}
        if any(len(grouped.get(name, [])) != 1 for name in legacy_names):
            return {'status': 'SKIP', 'reason': 'ambiguous file has an incomplete or repeated legacy contract'}
        legacy_sections = [grouped[name][0] for name in legacy_names]
        for section in legacy_sections:
            digest = hashlib.sha256(section['body'].encode('utf-8')).hexdigest()
            if digest != LEGACY_FULL_SECTION_SHA256[section['title']]:
                return {'status': 'SKIP', 'reason': f'ambiguous legacy {section["title"]} section'}

        newline = '\r\n' if '\r\n' in text else '\n'
        replacements = []
        for section in legacy_sections:
            if section['title'] == 'Grimoire Gate':
                replacement = _canonical_gate_section(section['level'], section['separator'], newline)
            else:
                replacement = None
            replacements.append((section, replacement))
        updated = _replace_sections(lines, replacements)
        return _make_upgrade_plan(project, original, updated)

    candidates = [section for section in sections if section['title'] in UPGRADE_HEADINGS]
    if not candidates:
        return {'status': 'SKIP', 'reason': 'no recognized Grimoire section'}
    if len(candidates) != 1:
        return {'status': 'SKIP', 'reason': 'ambiguous file has multiple Grimoire sections'}

    section = candidates[0]
    if section['title'] == 'Required wiki workflow':
        expected = _normalize_section(GATE.strip())
        expected = expected.removeprefix('## Required wiki workflow').strip()
        if section['body'] == expected:
            return {'status': 'UP-TO-DATE'}
        fingerprint = hashlib.sha256(section['body'].encode('utf-8')).hexdigest()
        if fingerprint not in STOCK_REQUIRED_WORKFLOW_SHA256:
            return {'status': 'SKIP', 'reason': 'ambiguous Required wiki workflow section'}

        newline = '\r\n' if '\r\n' in text else '\n'
        updated = _replace_sections(
            lines,
            [(section, _canonical_gate_section(section['level'], section['separator'], newline))],
        )
        return _make_upgrade_plan(project, original, updated)

    if section['body'] not in {_normalize_section(LEGACY_GRIMOIRE_GATE), _normalize_section(LEGACY_SETUP_GATE)}:
        return {'status': 'SKIP', 'reason': 'ambiguous Grimoire Gate section'}

    newline = '\r\n' if '\r\n' in text else '\n'
    updated = _replace_sections(
        lines,
        [(section, _canonical_gate_section(section['level'], section['separator'], newline))],
    )
    return _make_upgrade_plan(project, original, updated)


def apply_upgrade(plan):
    """Save the exact source bytes, then atomically replace AGENTS.md."""
    target = plan['target']
    if target.is_symlink() or not target.is_file():
        raise ValueError('AGENTS.md changed after planning')
    if target.read_bytes() != plan['original']:
        raise ValueError('AGENTS.md changed after planning')

    original_mode = stat.S_IMODE(target.stat().st_mode)
    backup_mode = 0o600
    backup = plan['backup']
    if backup.is_symlink():
        raise ValueError('rollback backup path changed after planning')
    if backup.exists():
        if not backup.is_file() or backup.read_bytes() != plan['original']:
            raise ValueError('rollback backup path changed after planning')
        os.chmod(backup, backup_mode)
    else:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        descriptor = os.open(backup, flags, backup_mode)
        try:
            os.fchmod(descriptor, backup_mode)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(plan['original'])
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                backup.unlink()
            except OSError:
                pass
            raise

    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=target.parent, prefix='.AGENTS.md.', delete=False) as stream:
            temporary_name = stream.name
            stream.write(plan['updated'])
        os.chmod(temporary_name, original_mode)
        if target.is_symlink() or not target.is_file() or target.read_bytes() != plan['original']:
            raise ValueError('AGENTS.md changed after planning')
        os.replace(temporary_name, target)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def upgrade_project(project, apply):
    """Print the upgrade decision and apply only an exact recognized section."""
    plan = plan_upgrade(project)
    status = plan['status']
    if status == 'UP-TO-DATE':
        print(f'UP-TO-DATE {project.name}: Required wiki workflow')
        return
    if status == 'SKIP':
        print(f'SKIP {project.name}: {plan["reason"]}')
        return

    print(f'{"APPLY" if apply else "PREVIEW"} {project.name}: AGENTS.md')
    if apply:
        apply_upgrade(plan)
        print(f'  rollback copy: {UPGRADE_BACKUP}')
    else:
        print(f'  rollback copy on apply: {UPGRADE_BACKUP}')
        before = plan['original'].decode('utf-8').splitlines(keepends=True)
        after = plan['updated'].decode('utf-8').splitlines(keepends=True)
        diff = difflib.unified_diff(
            before,
            after,
            fromfile=f'{project.name}/AGENTS.md (before)',
            tofile=f'{project.name}/AGENTS.md (after)',
            n=0,
        )
        for line in diff:
            print(line, end='')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects-root', type=Path, required=True)
    parser.add_argument('--scopes-json', type=Path, help='JSON object mapping project directory names to one-line scopes')
    parser.add_argument('--apply', action='store_true', help='write planned changes (default: preview only)')
    parser.add_argument('--upgrade', action='store_true', help='upgrade exact recognized Grimoire sections (default: preview only)')
    args = parser.parse_args()
    scopes = json.loads(args.scopes_json.read_text()) if args.scopes_json else {}
    if not isinstance(scopes, dict) or any(not isinstance(v, str) or '\n' in v or '\r' in v for v in scopes.values()):
        parser.error('scopes must be a JSON object containing one-line string values')
    if not args.projects_root.is_dir():
        parser.error('projects root must be an existing directory')
    for project in sorted(args.projects_root.iterdir()):
        if project.name.startswith('.') or project.name in SKIP or project.is_symlink() or not project.is_dir():
            continue
        if args.upgrade:
            try:
                upgrade_project(project, args.apply)
            except (ValueError, OSError, UnicodeError) as exc:
                print(f'SKIP {project.name}: {exc}')
            continue
        try:
            edits = plan_project(project, scopes.get(project.name, f'{project.name} project; detailed scope has not yet been documented.'))
        except (ValueError, OSError, UnicodeError) as exc:
            print(f'SKIP {project.name}: {exc}')
            continue
        print(f'{"APPLY" if args.apply else "PREVIEW"} {project.name}: {len(edits)} files')
        for relative, content in edits.items():
            print(f'  {relative}')
            if args.apply:
                target = project / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)


if __name__ == '__main__':
    main()
