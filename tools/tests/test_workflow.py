"""Exercise logged checks and guarded landing in disposable repositories only."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from project_common import WorkflowError, checkout_lock, tree_fingerprint
import project_config


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = load('check_helper', TOOLS / 'project-check.py')
FIXTURE_CONFIG = '''[project]
name = "Fixture"
cache_name = "fixture"

[[scopes]]
name = "docs"
paths = ["**/*.md"]
commands = [["python3", "tools/check-doc-links.py", "--changed", "--base", "{base}"]]

[[scopes]]
name = "code"
paths = ["src/**", "Makefile"]
commands = [
  { name = "code-lint", argv = ["python3", "-c", "pass"] },
  { name = "code-test", argv = ["python3", "-c", "pass"], cwd = "src" },
]
'''
LAND = load('land_helper', TOOLS / 'project_land.py')


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='project workflow ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'checkout with spaces'
        self.root.mkdir()
        self.remote = Path(self.tmp.name) / 'remote.git'
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.hooksPath', str(self.root / '.git/hooks'))
        (self.root / 'README.md').write_text('# Fixture\nBase\n')
        (self.root / 'tools').mkdir()
        for filename in ('check-doc-links.py', 'project_markdown.py', 'project-check.py', 'project_common.py', 'project_config.py'):
            shutil.copy2(TOOLS / filename, self.root / 'tools' / filename)
        (self.root / 'tools/project.toml').write_text(FIXTURE_CONFIG)
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: initial')
        subprocess.run(['git', 'init', '--bare', '-q', str(self.remote)], check=True)
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', '-qu', 'origin', 'main')
        self.git('switch', '-qc', 'feature')
        (self.root / 'change.md').write_text('[Readme](README.md#fixture)\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: feature')
        self.body = Path(self.tmp.name) / 'body with spaces.txt'
        self.body.write_text('Add documentation with verified checks.\n')
        self.counter = 0

    def git(self, *args, ok=True):
        r = subprocess.run(['git', '-C', str(self.root), *args], text=True, capture_output=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def cli(self, filename, *args):
        return subprocess.run([sys.executable, str(TOOLS / filename), *map(str, args)],
                              cwd=self.root, text=True, capture_output=True,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def evidence(self, extra=None, base='main'):
        self.counter += 1
        out = Path(self.tmp.name) / f'checks-{self.counter}'
        args = ['--base', base, '--run', '--output-dir', out]
        if extra:
            args += ['--extra-command', json.dumps(extra)]
        r = self.cli('project-check.py', *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return out / 'evidence.json'

    def landing(self, evidence=None, execute=True):
        args = ['feature', '--title', 'docs: landed', '--body-file', self.body]
        if evidence:
            args += ['--evidence', evidence]
        if execute:
            args += ['--execute']
        return self.cli('project_land.py', *args)

    def advance_main(self, filename='other.md', text='# Other\n'):
        self.git('switch', '-q', 'main')
        (self.root / filename).write_text(text)
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: advance main')
        self.git('push', '-q')
        self.git('switch', '-q', 'feature')

    def config(self, text=FIXTURE_CONFIG):
        (self.root / 'tools/project.toml').write_text(text)
        return project_config.load(self.root)

    def test_plan_does_not_execute_and_uses_configured_commands(self):
        (self.root / 'src').mkdir()
        (self.root / 'src/app.py').write_text('print(1)\n')
        r = self.cli('project-check.py', '--base', 'main', '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = json.loads(r.stdout)
        self.assertEqual([c['name'] for c in plan['commands']], ['whitespace', 'docs', 'code-lint', 'code-test'])
        self.assertEqual(plan['commands'][1]['argv'][-1], plan['base'])
        self.assertEqual(plan['commands'][3]['cwd'], 'src')
        self.assertFalse(plan['execute'])

    def test_whitespace_check_covers_untracked_files(self):
        (self.root / 'untracked.md').write_text('trailing \n')
        r = self.cli('project-check.py', '--whitespace-only', 'main')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('trailing whitespace', r.stdout + r.stderr)
        (self.root / 'untracked.md').write_text('clean\n')
        subprocess.run(['git', 'init', '-q', str(self.root / 'nested')], check=True)
        subprocess.run(['git', '-C', str(self.root / 'nested'), 'commit', '-q', '--allow-empty', '-m', 'n'], check=True,
                       env={**os.environ, 'GIT_AUTHOR_NAME': 'F', 'GIT_AUTHOR_EMAIL': 'f@example.invalid',
                            'GIT_COMMITTER_NAME': 'F', 'GIT_COMMITTER_EMAIL': 'f@example.invalid'})
        r = self.cli('project-check.py', '--whitespace-only', 'main')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('error', r.stdout + r.stderr)

    def test_fingerprint_binds_nested_repository_contents(self):
        nested = self.root / 'nested'
        env = {**os.environ, 'GIT_AUTHOR_NAME': 'F', 'GIT_AUTHOR_EMAIL': 'f@example.invalid',
               'GIT_COMMITTER_NAME': 'F', 'GIT_COMMITTER_EMAIL': 'f@example.invalid'}
        def nested_git(*args):
            subprocess.run(['git', '-C', str(nested), *args], check=True, capture_output=True, env=env)
        subprocess.run(['git', 'init', '-q', str(nested)], check=True)
        (nested / 'a.txt').write_text('one\n')
        nested_git('add', '.'); nested_git('commit', '-qm', 'n')
        self.git('add', 'nested')  # Recorded as a gitlink, like a checked-out submodule.
        seen = [tree_fingerprint(self.root)]
        self.assertEqual(tree_fingerprint(self.root), seen[0])
        (nested / 'a.txt').write_text('two\n')  # Uncommitted edit inside the submodule.
        seen.append(tree_fingerprint(self.root))
        (nested / 'new.txt').write_text('new\n')
        seen.append(tree_fingerprint(self.root))
        nested_git('add', '.'); nested_git('commit', '-qm', 'n2')
        seen.append(tree_fingerprint(self.root))
        self.assertEqual(len(set(seen)), 4, seen)

    def test_scopes_are_union_not_permission_to_skip_checks(self):
        config = self.config()
        scopes, unknown = CHECK.infer_scopes(config, ['src/a/b.py', 'docs/guide.md', 'README.md', 'Makefile'])
        self.assertEqual((scopes, unknown), ({'docs', 'code'}, []))
        self.assertEqual(CHECK.infer_scopes(config, ['image.bin', 'src.py']), (set(), ['image.bin', 'src.py']))
        commands = CHECK.command_plan(config, {'code'}, 'HEAD', [['true']])
        self.assertEqual([c['name'] for c in commands], ['whitespace', 'code-lint', 'code-test', 'extra-1'])
        r = self.cli('project-check.py', '--base', 'main', '--scope', 'missing')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Unknown --scope', r.stderr)
        r = self.cli('project-check.py', '--base', 'main', '--scope', 'code', '--json')
        self.assertIn('code-test', r.stdout)

    def test_glob_translation(self):
        cases = [('**/*.md', 'README.md', True), ('**/*.md', 'a/b/c.md', True), ('*.md', 'a/b.md', False),
                 ('src/**', 'src/a/b', True), ('src/**', 'srcx/a', False), ('a?c', 'abc', True), ('a?c', 'a/c', False),
                 ('docs/*.png', 'docs/x/y.png', False), ('file.txt', 'file_txt', False)]
        for pattern, path, expected in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(bool(project_config.glob_regex(pattern).match(path)), expected)

    def test_invalid_config_is_refused(self):
        bad = {
            'cwd escape': FIXTURE_CONFIG.replace('cwd = "src"', 'cwd = "../x"'),
            'absolute cwd': FIXTURE_CONFIG.replace('cwd = "src"', 'cwd = "/tmp"'),
            'duplicate scope': FIXTURE_CONFIG.replace('name = "code"', 'name = "docs"'),
            'cache name': FIXTURE_CONFIG.replace('cache_name = "fixture"', 'cache_name = "../x"'),
            'empty argv': FIXTURE_CONFIG.replace('["python3", "-c", "pass"], cwd', '[], cwd'),
            'syntax': FIXTURE_CONFIG + '[[scopes\n',
        }
        for label, text in bad.items():
            with self.subTest(label), self.assertRaises(WorkflowError):
                self.config(text)

    def test_main_branch_defaults_from_config(self):
        self.git('branch', '-m', 'main', 'trunk')
        self.git('switch', '-q', 'trunk')
        self.config(FIXTURE_CONFIG.replace('cache_name = "fixture"', 'cache_name = "fixture"\nmain_branch = "trunk"'))
        self.git('commit', '-qam', 'chore: use trunk')
        self.git('push', '-qu', 'origin', 'trunk')
        self.git('switch', '-q', 'feature')
        self.git('merge', '-q', 'trunk')
        r = self.cli('project_land.py', 'feature')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('feature -> trunk', r.stdout)

    def test_failed_checks_stop_and_retain_full_logs_and_nonzero_status(self):
        out = Path(self.tmp.name) / 'failed checks'
        commands = [
            {'name': 'fail', 'argv': [sys.executable, '-c', 'print("fixture failure"); raise SystemExit(7)'], 'cwd': '.'},
            {'name': 'unrun', 'argv': [sys.executable, '-c', 'raise SystemExit(0)'], 'cwd': '.'},
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code, path = CHECK.run_checks(self.root, commands, out, {'tree_fingerprint': tree_fingerprint(self.root)}, tail_lines=1)
        self.assertIn('STOP: remaining checks unrun', output.getvalue())
        self.assertEqual(code, 7)
        result = json.loads(path.read_text())
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['results']), 1)
        self.assertIn('fixture failure', Path(result['results'][0]['log']).read_text())

    def test_fingerprint_covers_untracked_source_and_file_mode(self):
        old = tree_fingerprint(self.root)
        p = self.root / 'extra.py'
        p.write_text('print(1)\n')
        new = tree_fingerprint(self.root)
        self.assertNotEqual(old, new)
        p.chmod(0o755)
        self.assertNotEqual(new, tree_fingerprint(self.root))

    def test_deleted_source_evidence_remains_fresh_after_commit(self):
        path = self.root / 'obsolete.md'
        path.write_text('# Obsolete\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: temporary source')
        path.unlink()
        before = tree_fingerprint(self.root)
        self.git('add', '-u')
        self.git('commit', '-qm', 'docs: delete temporary source')
        self.assertEqual(tree_fingerprint(self.root), before)

    def test_operation_lock_blocks_overlapping_checks(self):
        with checkout_lock(self.root):
            r = self.cli('project-check.py', '--run', '--output-dir', Path(self.tmp.name) / 'locked')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Another helper', r.stderr)

    def test_preview_is_read_only_and_execute_requires_evidence(self):
        head = self.git('rev-parse', 'HEAD').stdout
        remote = self.git('rev-parse', 'origin/main').stdout
        r = self.landing(execute=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('PREVIEW ONLY', r.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD').stdout, head)
        self.assertEqual(self.git('rev-parse', 'origin/main').stdout, remote)
        self.assertNotEqual(self.landing().returncode, 0)

    def test_dirty_stale_failed_or_partial_evidence_is_refused(self):
        path = self.evidence()
        original = path.read_text()
        (self.root / 'dirty.md').write_text('# Dirty\n')
        self.assertNotEqual(self.landing(path).returncode, 0)
        (self.root / 'dirty.md').unlink()
        for change in ('stale', 'failed', 'partial', 'missing-log'):
            evidence = json.loads(original)
            if change == 'stale':
                evidence['tree_fingerprint'] = '0' * 64
            elif change == 'failed':
                evidence['passed'] = False
            elif change == 'partial':
                evidence['commands'].pop()
                evidence['results'].pop()
            else:
                evidence['results'][0]['log'] = str(Path(self.tmp.name) / 'missing.log')
            path.write_text(json.dumps(evidence))
            r = self.landing(path)
            self.assertNotEqual(r.returncode, 0, change)
            self.assertEqual(self.git('branch', '--show-current').stdout.strip(), 'feature')
        path.write_text(original)

    def test_success_uses_configured_identity_pushes_and_retains_recovery(self):
        r = self.landing(self.evidence())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git('branch', '--show-current').stdout.strip(), 'main')
        self.assertNotEqual(self.git('show-ref', '--verify', 'refs/heads/feature', ok=False).returncode, 0)
        self.assertEqual(self.git('log', '-1', '--format=%an <%ae>').stdout.strip(), 'Fixture <fixture@example.invalid>')
        self.assertEqual(self.git('rev-parse', 'main').stdout, self.git('rev-parse', 'origin/main').stdout)
        self.assertIn('recovery/project-land-', self.git('branch', '--list', 'recovery/*').stdout)
        self.assertFalse(self.git('status', '--porcelain').stdout)

    def test_later_feature_baseline_cannot_hide_unchecked_document(self):
        (self.root / 'change.md').write_text('[Broken](missing.md)\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: unchecked broken link')
        partial_base = self.git('rev-parse', 'HEAD').stdout.strip()
        (self.root / 'later.md').write_text('# Later\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: later change')
        evidence = self.evidence(base=partial_base)
        main_before = self.git('rev-parse', 'main').stdout
        for execute in (False, True):
            result = self.landing(evidence, execute=execute)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('does not cover the entire branch', result.stderr)
        self.assertEqual(self.git('rev-parse', 'main').stdout, main_before)
        self.assertEqual(self.git('rev-parse', 'origin/main').stdout, main_before)
        self.assertFalse(self.git('branch', '--list', 'recovery/*').stdout)

    def test_older_baseline_cannot_hide_restored_document(self):
        old_base = self.git('rev-parse', 'main').stdout.strip()
        self.git('switch', '-q', 'main')
        (self.root / 'README.md').write_text('# Fixture\nNew base\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: update base')
        self.git('push', '-q')
        self.git('switch', '-q', 'feature')
        self.git('rebase', 'main')
        (self.root / 'README.md').write_text('# Fixture\nBase\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: restore old content')
        result = self.landing(self.evidence(base=old_base))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('omits feature paths', result.stderr)

    def test_older_baseline_with_complete_coverage_can_land(self):
        old_base = self.git('rev-parse', 'main').stdout.strip()
        self.advance_main()
        self.git('rebase', 'main')
        result = self.landing(self.evidence(base=old_base))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_evidence_uses_selected_landing_target(self):
        self.git('branch', '-m', 'main', 'trunk')
        evidence = self.evidence(base='trunk')
        result = self.cli('project_land.py', 'feature', '--main', 'trunk',
                          '--evidence', evidence, '--title', 'docs: landed',
                          '--body-file', self.body, '--execute')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git('branch', '--show-current').stdout.strip(), 'trunk')

    def test_fresh_diverged_main_evidence_rebases_and_reruns_checks(self):
        common_base = self.git('rev-parse', 'main').stdout.strip()
        self.advance_main()
        marker = Path(self.tmp.name) / 'fresh-check-count.txt'
        extra = [sys.executable, '-c', 'from pathlib import Path; p=Path(__import__("sys").argv[1]); p.write_text(p.read_text()+"check\\n" if p.exists() else "check\\n")', str(marker)]
        evidence = self.evidence(extra)
        data = json.loads(evidence.read_text())
        self.assertEqual(data['base'], common_base)
        self.assertEqual(data['changed_paths'], ['change.md'])
        self.assertEqual(self.landing(evidence, execute=False).returncode, 0)
        result = self.landing(evidence)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(marker.read_text().splitlines(), ['check', 'check'])
        self.assertTrue((self.root / 'other.md').exists())
        self.assertEqual(self.git('rev-parse', 'main').stdout, self.git('rev-parse', 'origin/main').stdout)

    def test_rebase_reruns_recorded_checks_before_landing(self):
        marker = Path(self.tmp.name) / 'check-count.txt'
        extra = [sys.executable, '-c', 'from pathlib import Path; p=Path(__import__("sys").argv[1]); p.write_text(p.read_text()+"check\\n" if p.exists() else "check\\n")', str(marker)]
        evidence = self.evidence(extra)
        self.advance_main()
        r = self.landing(evidence)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(marker.read_text().splitlines(), ['check', 'check'])
        self.assertTrue((self.root / 'other.md').exists())

    def test_rebased_check_failure_stops_before_squash(self):
        extra=[sys.executable, '-c', 'from pathlib import Path; raise SystemExit(3 if Path("other.md").exists() else 0)']
        self.advance_main()
        evidence=self.evidence(extra)
        main_before=self.git('rev-parse','main').stdout
        result=self.landing(evidence)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Rebased checks failed',result.stderr)
        self.assertEqual(self.git('rev-parse','main').stdout,main_before)
        self.assertEqual(self.git('branch','--show-current').stdout.strip(),'feature')
        self.assertFalse(self.git('status','--porcelain').stdout)

    def test_upstream_is_required_and_main_worktree_is_respected(self):
        self.git('config','--unset','branch.main.remote')
        result=self.landing(execute=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('configured upstream',result.stderr)
        self.git('config','branch.main.remote','origin')
        other=Path(self.tmp.name)/'main worktree'
        self.git('worktree','add','-q',str(other),'main')
        result=self.landing(execute=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('another worktree',result.stderr)

    def test_conflict_aborts_rebase_without_landing(self):
        (self.root / 'README.md').write_text('# Fixture\nFeature edit\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'docs: conflict fixture')
        evidence = self.evidence()
        old = self.git('rev-parse', 'HEAD').stdout
        self.advance_main('README.md', '# Fixture\nMain edit\n')
        r = self.landing(evidence)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Rebase failed and was aborted', r.stderr)
        self.assertIn('README.md', r.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD').stdout, old)
        self.assertFalse(self.git('status', '--porcelain').stdout)

    def test_commit_hook_rejection_does_not_push_or_delete_feature(self):
        evidence = self.evidence()
        hook = self.root / '.git/hooks/commit-msg'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        old = self.git('rev-parse', 'main').stdout
        r = self.landing(evidence)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Squash commit failed', r.stderr)
        self.assertEqual(self.git('rev-parse', 'main').stdout, old)
        self.git('show-ref', '--verify', 'refs/heads/feature')

    def test_push_rejection_retains_local_main_feature_and_recovery(self):
        evidence = self.evidence()
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        old = self.git('rev-parse', 'origin/main').stdout
        r = self.landing(evidence)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Push failed', r.stderr)
        self.assertNotEqual(self.git('rev-parse', 'main').stdout, old)
        self.git('show-ref', '--verify', 'refs/heads/feature')

    def test_hook_changed_commit_tree_stops_before_push(self):
        evidence=self.evidence()
        hook=self.root/'.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nprintf "fixture formatter change\n" >> README.md\ngit add README.md\n')
        hook.chmod(0o755)
        old=self.git('rev-parse','origin/main').stdout
        result=self.landing(evidence)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('differs from the verified feature tree',result.stderr)
        self.assertEqual(self.git('rev-parse','origin/main').stdout,old)
        self.git('show-ref','--verify','refs/heads/feature')

    def test_commit_hook_source_changes_stop_before_push(self):
        evidence = self.evidence()
        hook = self.root / '.git/hooks/post-commit'
        hook.write_text('#!/bin/sh\nprintf "changed by fixture hook\\n" >> README.md\n')
        hook.chmod(0o755)
        old = self.git('rev-parse', 'origin/main').stdout
        r = self.landing(evidence)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('hook left working changes', r.stderr)
        self.assertEqual(self.git('rev-parse', 'origin/main').stdout, old)
        self.git('show-ref', '--verify', 'refs/heads/feature')


if __name__ == '__main__':
    unittest.main()
