"""Exercise automatic adoption through the actual refresh shell entry point."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/refresh-wiki-rag.sh'


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.projects = self.root / 'projects'
        self.project = self.projects / 'new app'
        self.project.mkdir(parents=True)
        self.uv = self.root / 'uv'
        # Run the real setup script; replace only the indexer with an observation
        # of the state at its boundary, so ordering failures are visible.
        self.uv.write_text('''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
assert args[:2] == ['run', '--directory'], args
args = args[3:]
if args[0] == 'python':
    sys.exit(subprocess.call([os.environ['TEST_PYTHON'], *args[1:]]))
assert args == ['grimoire-mcp', 'reindex', '*'], args
project = pathlib.Path(os.environ['TEST_PROJECT'])
pathlib.Path(os.environ['TEST_RESULT']).write_text(json.dumps({
    'wiki': (project / 'wiki/README.md').is_file(),
    'agents': (project / 'AGENTS.md').is_file(),
}))
''')
        self.uv.chmod(0o755)
        self.result = self.root / 'indexed.json'
        self.env = dict(os.environ,
            GRIMOIRE_WIKI_RAG_CONFIG=str(self.root / 'absent.env'),
            WIKI_RAG_PROJECTS_ROOT=str(self.projects),
            WIKI_RAG_HOME=str(self.root / 'index'),
            UV_BIN=str(self.uv), TEST_PYTHON=sys.executable,
            TEST_PROJECT=str(self.project), TEST_RESULT=str(self.result),
            WIKI_RAG_AUTO_SETUP='0', GRIMOIRE_WIKI_RAG_DRY_RUN='0')

    def refresh(self, **settings):
        result = subprocess.run(['bash', str(SCRIPT)], env={**self.env, **settings},
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_auto_setup_precedes_index_and_preserves_existing_content(self):
        original = b'# Project rules\nPreserve this.\n'
        (self.project / 'AGENTS.md').write_bytes(original)
        self.refresh(WIKI_RAG_AUTO_SETUP='1')
        import json
        self.assertEqual(json.loads(self.result.read_text()), {'wiki': True, 'agents': True})
        self.assertTrue((self.project / 'AGENTS.md').read_bytes().startswith(original))
        before = {p: p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        self.refresh(WIKI_RAG_AUTO_SETUP='1')
        self.assertEqual(before, {p: p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

    def test_disabled_setup_only_indexes(self):
        self.refresh()
        self.assertTrue(self.result.exists())
        self.assertFalse((self.project / 'wiki').exists())
        self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_dry_run_does_not_create_wiki_or_index(self):
        output = self.refresh(WIKI_RAG_AUTO_SETUP='1', GRIMOIRE_WIKI_RAG_DRY_RUN='1')
        self.assertIn('setup-projects.py', output)
        self.assertFalse((self.project / 'wiki').exists())
        self.assertFalse(self.result.exists())
        self.assertFalse((self.root / 'index').exists())


if __name__ == '__main__':
    unittest.main()
