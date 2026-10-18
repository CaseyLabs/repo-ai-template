"""Copy the current template checkout (including uncommitted edits) into a disposable repository."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def git(root, *args, ok=True):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    if ok and result.returncode:
        raise AssertionError(result.stderr)
    return result


def copy_template(dest):
    """Create a committed copy of the template's tracked and untracked (not ignored) files at dest."""
    raw = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                         capture_output=True, check=True).stdout
    dest.mkdir(parents=True)
    for name in sorted({os.fsdecode(p) for p in raw.split(b'\0') if p}):
        source, target = ROOT / name, dest / name
        if not source.is_symlink() and not source.exists():
            continue  # Deleted in the working tree.
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        else:
            shutil.copy2(source, target)
    for args in (('init', '-q', '-b', 'main'), ('config', 'user.name', 'Fixture'),
                 ('config', 'user.email', 'fixture@example.invalid'), ('config', 'core.hooksPath', '.git/hooks'),
                 ('add', '-A'), ('commit', '-qm', 'chore: template')):
        git(dest, *args)
    return dest
