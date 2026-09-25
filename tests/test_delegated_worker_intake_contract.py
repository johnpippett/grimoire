from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE_GUIDANCE_FILES = (
    ROOT / 'AGENTS.md',
    ROOT / 'README.md',
    ROOT / 'skills/grimoire-intake/SKILL.md',
    ROOT / 'skills/grimoire-update/SKILL.md',
    ROOT / 'wiki-template/README.md',
    ROOT / 'docs/grimoire-wiki-rag-setup.md',
)
SKILLS_INDEX = ROOT / 'skills/README.md'
ALL_GUIDANCE_FILES = (*CORE_GUIDANCE_FILES, SKILLS_INDEX)


class DelegatedWorkerIntakeContractTests(unittest.TestCase):
    def read(self, path):
        return ' '.join(path.read_text().split())

    def test_full_initial_wiki_read_is_for_agents_working_alone_and_coordinators(self):
        for path in CORE_GUIDANCE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path).lower()
                self.assertIn('agent that works alone', text)
                self.assertIn('coordinat', text)
                self.assertIn('wiki/README.md'.lower(), text)
                self.assertRegex(text, r'notes? (?:for|about|on) (?:the )?(?:task )?topic')

    def test_delegated_worker_may_use_sufficient_coordinator_context(self):
        for path in CORE_GUIDANCE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path).lower()
                self.assertIn('worker', text)
                self.assertIn('coordinator', text)
                self.assertIn('wiki context', text)
                self.assertIn('sufficient', text)
                self.assertIn('source paths', text)
                self.assertRegex(text, r'(?:only )?when needed')

    def test_continuing_workers_can_use_new_context_after_topic_or_context_change(self):
        for path in CORE_GUIDANCE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path).lower()
                self.assertIn('initial wiki read', text)
                self.assertIn('topic change', text)
                self.assertIn('context loss', text)
                self.assertIn('continuing worker', text)
                self.assertIn('agent that works alone', text)
                self.assertIn('new, sufficient wiki context', text)
                self.assertRegex(text, r'(?:reads?|read) more notes only when needed')

    def test_indexed_facts_require_active_checkout_and_complete_passages(self):
        for path in CORE_GUIDANCE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path).lower()
                self.assertIn('active checkout', text)
                self.assertIn('incomplete', text)
                self.assertIn('read_wiki_passage', text)
                self.assertIn('generation', text)
                self.assertIn('chunk id', text)

    def test_coordinator_makes_final_wiki_edits_and_can_assign_a_note(self):
        for path in ALL_GUIDANCE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path).lower()
                self.assertIn('coordinator', text)
                self.assertRegex(text, r'makes? (?:the )?final wiki edits')
                self.assertIn('assigns note numbers', text)
                self.assertIn('updates the session log', text)
                self.assertRegex(
                    text,
                    r'(?:only when.*coordinator assigns|unless (?:it )?assigns .*note|unless assigned .*note)',
                )

    def test_initial_orientation_has_no_unqualified_task_start_sentence(self):
        generic_starts = (
            'at task start, agents read `wiki/readme.md`',
            'at the start of a task, read `wiki/readme.md`',
            'at the start of a task, the agent reads `wiki/readme.md`',
        )
        for path in ALL_GUIDANCE_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = self.read(path).lower()
                for wording in generic_starts:
                    self.assertNotIn(wording, text)

    def test_skills_index_scopes_intake_and_wiki_handoff(self):
        text = self.read(SKILLS_INDEX).lower()
        for phrase in (
            'agent works alone', 'coordinat', 'grimoire-intake', 'worker',
            'wiki context', 'source paths', 'when needed',
            'return findings', 'makes final wiki edits', 'assign a specific note',
            'topic change', 'context loss',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
