"""Tests for the commit-msg hook and the CI range check that reruns it."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
GIT_ENV = {**os.environ, 'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
           'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'}
TRAILER = 'Co-Authored-By: ' + 'Claude <noreply@example.invalid>'


class CommitMessages(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='commit messages ')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'checkout with spaces'
        (self.root / '.githooks').mkdir(parents=True)
        (self.root / 'tools').mkdir()
        shutil.copy2(REPO / '.githooks/commit-msg', self.root / '.githooks/commit-msg')
        shutil.copy2(REPO / 'tools/check-commit-messages.sh', self.root / 'tools/check-commit-messages.sh')
        self.git('init', '-q', '-b', 'main')
        self.git('add', '.')
        self.git('commit', '-qm', 'chore: initial')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, env=GIT_ENV, check=True, capture_output=True, text=True)

    def hook(self, message):
        path = self.root / 'message.txt'
        path.write_text(message)
        return subprocess.run(['sh', str(self.root / '.githooks/commit-msg'), str(path)], capture_output=True, text=True)

    def check(self, revisions):
        return subprocess.run(['sh', str(self.root / 'tools/check-commit-messages.sh'), revisions],
                              cwd=self.root, capture_output=True, text=True)

    def test_hook_rejects_trailer_and_ignores_comments_and_verbose_diff(self):
        r = self.hook(f'feat: x\n\n# comment\n{TRAILER}\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn('4:', r.stderr)  # Line numbers match the message file.
        diff = f'# ------------------------ >8 ------------------------\n+{TRAILER}\n'
        self.assertEqual(self.hook(f'feat: x\n\n# {TRAILER}\n{diff}').returncode, 0)

    def test_range_check_catches_commit_that_bypassed_hook(self):
        self.git('commit', '-q', '--allow-empty', '-m', 'feat: clean')
        self.assertEqual(self.check('HEAD~1..HEAD').returncode, 0)
        self.git('commit', '-q', '--allow-empty', '-m', f'feat: bad\n\n{TRAILER}')
        self.git('commit', '-q', '--allow-empty', '-m', 'fix: later')
        r = self.check('HEAD~3..HEAD')
        self.assertEqual(r.returncode, 1)
        self.assertIn('feat: bad', r.stderr)
        self.assertNotIn('fix: later', r.stderr)
        self.assertNotEqual(self.check('no-such-ref..HEAD').returncode, 0)

    def test_range_check_scans_hash_lines_kept_by_verbatim_cleanup(self):
        generated = 'Generated with ' + 'Claude Code'
        message = f'feat: x\n\n# {generated}\n# ------------------------ >8 ------------------------\n{TRAILER}\n'
        self.git('commit', '-q', '--allow-empty', '--cleanup=verbatim', '-m', message)
        r = self.check('HEAD~1..HEAD')
        self.assertEqual(r.returncode, 1)
        self.assertIn(generated, r.stderr)
        self.assertIn(TRAILER, r.stderr)


if __name__ == '__main__':
    unittest.main()
