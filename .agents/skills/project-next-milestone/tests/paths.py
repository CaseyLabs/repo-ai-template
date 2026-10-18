"""Portable path smoke checks for the milestone skill; no network or account access."""
import pathlib
import shutil
import subprocess
import sys
import tempfile

repo = pathlib.Path(__file__).resolve().parents[4]


def run(*args, cwd=repo, ok=True):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert (result.returncode == 0) == ok, result.stderr + result.stdout
    return result.stdout + result.stderr


with tempfile.TemporaryDirectory(prefix='project paths ') as tmp:
    worktree = pathlib.Path(tmp) / 'work tree'
    run('git', 'worktree', 'add', '--detach', str(worktree), 'HEAD')
    try:
        # Test the current edited resources, not only HEAD's earlier versions.
        for tree in ['.agents/skills', 'tools']:
            shutil.copytree(repo / tree, worktree / tree, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__'))
        for checkout in [repo, worktree]:
            context = checkout / 'tools/project-context.py'
            for cwd in [checkout, checkout / 'docs']:
                for tree in ['.agents/skills', '.claude/skills']:
                    base = checkout / tree
                    assert run('git', '-C', str(base), 'rev-parse', '--show-toplevel', cwd=cwd).strip() == str(checkout)
                    for item in (checkout / '.agents/skills').rglob('*'):
                        if item.is_file():
                            assert item.samefile(base / item.relative_to(checkout / '.agents/skills')), item
                plan = 'PLAN.md' if cwd == checkout else '../PLAN.md'
                assert 'Portfolio' in run(sys.executable, str(context), '--plan', plan, cwd=cwd)
                assert 'Portfolio' in run(sys.executable, str(context), '--plan', str(checkout / 'PLAN.md'), cwd=cwd)
                run(sys.executable, str(context), '--plan', 'missing plan.md', cwd=cwd, ok=False)
    finally:
        run('git', 'worktree', 'remove', '--force', str(worktree))
print('PASS relative/absolute/missing plans; root/subdirectory/worktree skill resource identity')
