"""Break a disposable copy of the template in known ways and check that ai-check notices each one."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template_fixture import copy_template  # noqa: E402


class AiCheck(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='project ai-check ')
        self.addCleanup(tmp.cleanup)
        self.root = copy_template(Path(tmp.name) / 'checkout with spaces')

    def check(self, *args):
        return subprocess.run([sys.executable, str(self.root / 'tools/ai-check.py'), *args], cwd=self.root,
                              capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def assert_fails(self, text, *args):
        result = self.check('--template', *args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(text, result.stdout)

    def edit(self, name, old, new):
        path = self.root / name
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_clean_setup_passes_and_placeholders_fail_outside_template_mode(self):
        result = self.check('--template')
        self.assertEqual(result.returncode, 0, result.stdout)
        if not (self.root / 'TEMPLATE.md').exists():  # An initialized project has no placeholders left.
            (self.root / 'README.md').write_text('# {{' + 'PROJECT_NAME}}\n')
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn('README.md:1: unfilled template placeholder', result.stdout)
        self.assertIn('WARN: core.hooksPath', result.stdout)

    def test_symlink_replaced_by_file(self):
        link = self.root / '.claude/skills'
        link.unlink()
        link.write_text('../.agents/skills\n')
        self.assert_fails('.claude/skills must be a symlink')

    def test_symlink_wrong_target(self):
        link = self.root / '.claude/skills'
        link.unlink()
        link.symlink_to('../.agents')
        self.assert_fails('not ../.agents/skills')

    def test_non_portable_skill_key(self):
        self.edit('.agents/skills/project-handoff/SKILL.md', 'name: project-handoff\n', 'name: project-handoff\nmodel: sonnet\n')
        self.assert_fails('non-portable frontmatter keys model')
        self.edit('.agents/skills/project-handoff/SKILL.md', 'model: sonnet\n', 'allowed-tools: Bash\n')
        self.assert_fails('non-portable frontmatter keys allowed-tools')

    def test_skill_name_must_match_folder(self):
        self.edit('.agents/skills/project-ship/SKILL.md', 'name: project-ship', 'name: ship')
        self.assert_fails("must match its folder 'project-ship'")

    def test_missing_codex_agent(self):
        (self.root / '.codex/agents/project-worker.toml').unlink()
        self.assert_fails('Claude agent project-worker has no matching .codex/agents/project-worker.toml')

    def test_missing_shared_instructions(self):
        (self.root / '.agents/skills/project-finish-milestone/references/worker.md').unlink()
        self.assert_fails('references/worker.md does not exist')

    def test_model_table_drift(self):
        self.edit('.claude/agents/project-worker.md', 'model: sonnet', 'model: opus')
        self.assert_fails("project-worker (claude): agent file has ('opus', 'medium'), table has ('sonnet', 'medium')")

    def test_claude_md_with_policy_text(self):
        (self.root / 'CLAUDE.md').write_text('@AGENTS.md\n\nAlways use tabs.\n')
        self.assert_fails('CLAUDE.md must contain only @ imports')

    def test_agents_md_budget(self):
        with (self.root / 'AGENTS.md').open('a') as stream:
            stream.write('- filler rule\n' * 60)
        self.assert_fails('AGENTS.md is')

    def test_broken_link_in_skill(self):
        with (self.root / '.agents/skills/project-ship/SKILL.md').open('a') as stream:
            stream.write('\nSee [missing](../../../docs/MISSING.md).\n')
        self.assert_fails('missing link target ../../../docs/MISSING.md')


if __name__ == '__main__':
    unittest.main()
