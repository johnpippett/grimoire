from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

SETUP = Path(__file__).resolve().parents[1] / 'setup.sh'


class SetupScriptTests(unittest.TestCase):
    def test_bootstrap_guidance_uses_wiki_orientation_without_scope_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'app'
            result = subprocess.run(
                ['bash', str(SETUP), str(project)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((project / 'wiki/README.md').is_file())
            self.assertIn('Read wiki/README.md and notes related to the task', result.stdout)
            self.assertIn('Search the wiki before asking the user to repeat a decision', result.stdout)
            self.assertIn('After meaningful work, update a topic note', result.stdout)
            self.assertIn('add one short link to the session log', result.stdout)
            self.assertIn('Write a one-sentence project summary in wiki/README.md from project files when clear', result.stdout)
            self.assertIn('Ask the user only if its purpose remains unclear', result.stdout)
            self.assertNotIn('Ask the user:', result.stdout)
            self.assertNotIn('full Grimoire workflow', result.stdout)
            evidence_path = os.environ.get('GRIMOIRE_SETUP_EVIDENCE')
            if evidence_path:
                Path(evidence_path).write_text(json.dumps({
                    'setup': 'Temporary project without a wiki directory; run setup.sh against that project.',
                    'steps': ['run bash setup.sh <temporary-project>', 'verify wiki/README.md and inspect the next-step output'],
                    'stdout': result.stdout,
                    'wiki_readme_created': (project / 'wiki/README.md').is_file(),
                    'old_scope_prompt_removed': 'What does this project do?' not in result.stdout,
                    'rerun': 'GRIMOIRE_SETUP_EVIDENCE=/tmp/grimoire-setup-e2e.json python tests/test_setup_script.py',
                }, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
