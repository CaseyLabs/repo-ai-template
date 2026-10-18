"""Initialize disposable copies of the template; init-project.py removes this file from new projects."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template_fixture import copy_template, git  # noqa: E402

TOOLS = Path(__file__).resolve().parents[1]
ENV = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}


class Init(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='project init ')
        self.addCleanup(tmp.cleanup)
        self.root = copy_template(Path(tmp.name) / 'demo checkout')

    def init(self, *args):
        return subprocess.run([sys.executable, str(TOOLS / 'init-project.py'), '--name', 'Demo App', '--slug', 'demo',
                               '--description', 'A demo project.', *args],
                              cwd=self.root, capture_output=True, text=True, env=ENV)

    def test_initializes_and_passes_ai_check(self):
        result = self.init('--scope', 'code:src/**,tests/**:make test', '--scope', 'lint:*.py:ruff check .',
                           '--setup', 'make setup', '--main-branch', 'trunk')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ai-check: 0 error(s), 0 warning(s)', result.stdout)
        for name in ('TEMPLATE.md', 'tools/init-project.py', 'tools/tests/test_init.py', '.agents/skills/project-run-app'):
            self.assertFalse((self.root / name).exists(), name)
        config = tomllib.loads((self.root / 'tools/project.toml').read_text())
        self.assertEqual(config['project'], {'name': 'Demo App', 'main_branch': 'trunk', 'cache_name': 'demo'})
        scopes = {s['name']: s for s in config['scopes']}
        self.assertEqual(list(scopes), ['docs', 'tooling', 'code', 'lint'])
        self.assertEqual(scopes['code'], {'name': 'code', 'paths': ['src/**', 'tests/**'], 'commands': [['make', 'test']]})
        self.assertNotIn('--template', str(scopes['tooling']['commands']))
        ci = (self.root / '.github/workflows/ci.yml').read_text()
        self.assertIn('run: python3 tools/ai-check.py\n', ci)
        self.assertNotIn('--template', ci)
        agents = (self.root / 'AGENTS.md').read_text()
        self.assertIn('Demo App: A demo project.', agents)
        self.assertIn('- `make test`: checks the `code` scope (`src/**`, `tests/**`).', agents)
        self.assertIn('`trunk`', agents)
        self.assertIn('```bash\nmake setup\n```', (self.root / 'CONTRIBUTING.md').read_text())
        self.assertEqual(git(self.root, 'config', 'core.hooksPath').stdout.strip(), '.githooks')

        # The new project's own checks pass, and a second init refuses without changing anything.
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-qm', 'chore: initialize Demo App')
        for argv in (['-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py'],
                     ['.agents/skills/project-next-milestone/tests/paths.py'], ['tools/check-doc-links.py', '--all']):
            check = subprocess.run([sys.executable, *argv], cwd=self.root, capture_output=True, text=True, env=ENV)
            self.assertEqual(check.returncode, 0, argv + [check.stdout[-2000:], check.stderr[-2000:]])
        head = git(self.root, 'rev-parse', 'HEAD').stdout
        again = self.init()
        self.assertEqual(again.returncode, 1)
        self.assertIn('already initialized', again.stderr)
        self.assertEqual(git(self.root, 'status', '--porcelain').stdout, '')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD').stdout, head)

    def test_hook_rejects_ai_attribution_after_init(self):
        self.assertEqual(self.init().returncode, 0)
        git(self.root, 'add', '-A')
        result = git(self.root, 'commit', '-qm', 'chore: init\n\nCo-Authored-By: Claude <noreply@anthropic.com>', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Co-Authored-By', result.stderr)

    def test_keep_run_app_renames_skill(self):
        result = self.init('--keep-run-app', 'demo')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        skill = (self.root / '.agents/skills/run-demo/SKILL.md').read_text()
        self.assertIn('name: run-demo', skill)
        self.assertIn('Run Demo App locally', skill)

    def test_refuses_dirty_tree_and_bad_input_without_changes(self):
        (self.root / 'stray.txt').write_text('x\n')
        result = self.init()
        self.assertIn('Commit or stash', result.stderr)
        (self.root / 'stray.txt').unlink()
        for args in (['--scope', 'docs:*.md:true'], ['--scope', 'bad'], ['--slug', 'Bad Slug'],
                     ['--main-branch=-x'], ['--keep-run-app', 'Bad Name']):
            with self.subTest(args=args):
                result = self.init(*args)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(git(self.root, 'status', '--porcelain').stdout, '')


if __name__ == '__main__':
    unittest.main()
