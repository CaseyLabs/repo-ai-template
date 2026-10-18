#!/usr/bin/env python3
"""Check that the shared Claude Code / Codex setup is intact: symlink, skills, agents, guidance and models."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_common import WorkflowError, repository  # noqa: E402
from project_markdown import links, resolve_target  # noqa: E402

# AGENTS.md is loaded into every session in both hosts; Codex stops reading at
# project_doc_max_bytes (32 KiB by default). Keep it far below that.
AGENTS_MAX_LINES = 100
AGENTS_MAX_BYTES = 12 * 1024
# https://agentskills.io/specification: portable SKILL.md frontmatter keys.
SKILL_KEYS = {'name', 'description', 'license', 'compatibility', 'metadata'}
SKILL_NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
PLACEHOLDER = re.compile(r'\{\{[A-Z][A-Z0-9_]*\}\}')
INSTRUCTIONS = re.compile(r'\.agents/skills/[\w./-]+\.md')
NO_VALUE = '-'
# Hard rules from AGENTS.md; each flag is denied in any argument position.
REQUIRED_DENY = {
    'Bash(git push --force*)', 'Bash(git push * --force*)', 'Bash(git push -f*)', 'Bash(git push * -f*)',
    'Bash(git commit --no-verify*)', 'Bash(git commit * --no-verify*)',
    'Bash(git commit -n*)', 'Bash(git commit * -n*)',  # -n is short for --no-verify.
}


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


def frontmatter(path):
    """Return the top-level keys of a `---` YAML frontmatter block (scalar values only), or None."""
    lines = path.read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != '---':
        return None
    data = {}
    for line in lines[1:]:
        if line == '---':
            return data
        if line[:1] in (' ', '\t', '-', '#') or not line.strip():
            continue  # Nested values (for example under metadata:) and comments.
        key, sep, value = line.partition(':')
        if sep:
            data[key.strip()] = value.strip().strip('"\'')
    return None


def check_symlink(root, report):
    link = root / '.claude/skills'
    if not link.is_symlink():
        report.error('.claude/skills must be a symlink to ../.agents/skills (on Windows, clone with core.symlinks=true)')
    elif os.readlink(link) != '../.agents/skills':
        report.error(f'.claude/skills points to {os.readlink(link)}, not ../.agents/skills')
    elif not (link.resolve() == (root / '.agents/skills').resolve()):
        report.error('.claude/skills does not resolve to .agents/skills')


def check_skills(root, report):
    skills = root / '.agents/skills'
    if not skills.is_dir():
        report.error('Missing .agents/skills')
        return
    for folder in sorted(p for p in skills.iterdir() if p.is_dir()):
        skill = folder / 'SKILL.md'
        where = skill.relative_to(root)
        if not skill.is_file():
            report.error(f'{folder.relative_to(root)} has no SKILL.md')
            continue
        data = frontmatter(skill)
        if data is None:
            report.error(f'{where}: missing or unterminated frontmatter')
            continue
        if data.get('name') != folder.name:
            report.error(f'{where}: name {data.get("name")!r} must match its folder {folder.name!r}')
        if not SKILL_NAME.fullmatch(folder.name) or len(folder.name) > 64:
            report.error(f'{where}: skill names are lowercase words joined by hyphens, at most 64 characters')
        if not data.get('description') or len(data['description']) > 1024:
            report.error(f'{where}: description must be 1-1024 characters')
        extra = sorted(set(data) - SKILL_KEYS)
        if extra:
            report.error(f'{where}: non-portable frontmatter keys {", ".join(extra)} (set host-specific options in host adapters)')


def check_instructions(root, path, text, report):
    referenced = INSTRUCTIONS.findall(text)
    if not referenced:
        report.error(f'{path.relative_to(root)}: does not reference a shared instructions file under .agents/skills/')
    for name in referenced:
        if not (root / name).is_file():
            report.error(f'{path.relative_to(root)}: instructions file {name} does not exist')


def agents(root, report):
    """Return {name: {'claude': (model, effort) | None, 'codex': (model, effort) | None}}."""
    found = {}
    for path in sorted((root / '.claude/agents').glob('*.md')):
        data = frontmatter(path) or {}
        if data.get('name') != path.stem:
            report.error(f'{path.relative_to(root)}: name must match the file name')
        found.setdefault(path.stem, {'claude': None, 'codex': None})['claude'] = (data.get('model', ''), data.get('effort', ''))
        check_instructions(root, path, path.read_text(encoding='utf-8'), report)
    for path in sorted((root / '.codex/agents').glob('*.toml')):
        try:
            data = tomllib.loads(path.read_text(encoding='utf-8'))
        except tomllib.TOMLDecodeError as error:
            report.error(f'{path.relative_to(root)}: invalid TOML: {error}')
            continue
        if data.get('name') != path.stem:
            report.error(f'{path.relative_to(root)}: name must match the file name')
        for key in ('description', 'developer_instructions'):
            if not data.get(key):
                report.error(f'{path.relative_to(root)}: missing {key}')
        found.setdefault(path.stem, {'claude': None, 'codex': None})['codex'] = (
            data.get('model', ''), data.get('model_reasoning_effort', ''))
        if path.stem.startswith('project-'):
            check_instructions(root, path, data.get('developer_instructions', ''), report)
    for name, hosts in found.items():
        if hosts['claude'] and not hosts['codex']:
            report.error(f'Claude agent {name} has no matching .codex/agents/{name}.toml')
    return found


def model_table(root, report):
    doc = root / 'docs/AI_SETUP.md'
    if not doc.is_file():
        report.error('Missing docs/AI_SETUP.md (model routing table)')
        return {}
    rows, inside = {}, False
    for line in doc.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            inside = line.strip() == '## Model routing'
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')] if inside and line.startswith('|') else []
        if len(cells) == 5 and cells[0] not in ('Agent', '') and not set(cells[0]) <= set('-: '):
            rows[cells[0]] = {'claude': None if cells[1] == NO_VALUE else (cells[1], cells[2]),
                              'codex': None if cells[3] == NO_VALUE else (cells[3], cells[4])}
    if not rows:
        report.error('docs/AI_SETUP.md: no rows found in the "## Model routing" table')
    return rows


def check_models(found, table, report):
    for name in sorted(set(found) | set(table)):
        if name not in table:
            report.error(f'Agent {name} is missing from the docs/AI_SETUP.md model routing table')
            continue
        if name not in found:
            report.error(f'Model routing table lists {name}, but no agent file defines it')
            continue
        for host in ('claude', 'codex'):
            if found[name][host] != table[name][host]:
                report.error(f'{name} ({host}): agent file has {found[name][host] or "no agent"}, '
                             f'table has {table[name][host] or "no agent"}')


def check_guidance(root, report):
    claude = root / 'CLAUDE.md'
    if not claude.is_file():
        report.error('Missing CLAUDE.md (it should contain only @AGENTS.md)')
    else:
        lines = [line.strip() for line in claude.read_text(encoding='utf-8').splitlines() if line.strip()]
        if '@AGENTS.md' not in lines or any(not line.startswith('@') for line in lines):
            report.error('CLAUDE.md must contain only @ imports, including @AGENTS.md; put policy in AGENTS.md')
    agents_md = root / 'AGENTS.md'
    if not agents_md.is_file():
        report.error('Missing AGENTS.md')
        return
    raw = agents_md.read_bytes()
    lines = raw.count(b'\n')
    if lines > AGENTS_MAX_LINES or len(raw) > AGENTS_MAX_BYTES:
        report.error(f'AGENTS.md is {lines} lines / {len(raw)} bytes; budget is {AGENTS_MAX_LINES} lines / '
                     f'{AGENTS_MAX_BYTES} bytes. Move procedures to the docs that own them.')
    settings = root / '.claude/settings.json'
    if settings.is_file():
        try:
            data = json.loads(settings.read_text(encoding='utf-8'))
        except ValueError as error:
            report.error(f'.claude/settings.json is not valid JSON: {error}')
            return
        missing = REQUIRED_DENY - set(data.get('permissions', {}).get('deny', []))
        for rule in sorted(missing):
            report.error(f'.claude/settings.json is missing deny rule {rule}')


def check_links(root, report):
    sources = [root / 'AGENTS.md', *sorted((root / '.agents/skills').rglob('*.md')), *sorted((root / '.claude/agents').glob('*.md'))]
    for source in sources:
        if not source.is_file():
            continue
        for line, dest in links(source.read_text(encoding='utf-8')):
            target, _ = resolve_target(source, dest, root)
            if target is not None and not target.exists():
                report.error(f'{source.relative_to(root)}:{line}: missing link target {dest}')


def tracked_files(root):
    raw = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                         cwd=root, capture_output=True, check=True).stdout
    return [os.fsdecode(p) for p in raw.split(b'\0') if p]


def check_initialized(root, report):
    for name in tracked_files(root):
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for match in PLACEHOLDER.findall(line):
                report.error(f'{name}:{number}: unfilled template placeholder {match}')
    hooks = subprocess.run(['git', 'config', '--get', 'core.hooksPath'], cwd=root, capture_output=True, text=True).stdout.strip()
    if hooks != '.githooks':
        report.warn('core.hooksPath is not .githooks; run `git config core.hooksPath .githooks` to enable the commit-msg hook')


def run(root, template):
    report = Report()
    check_symlink(root, report)
    check_skills(root, report)
    check_models(agents(root, report), model_table(root, report), report)
    check_guidance(root, report)
    check_links(root, report)
    if not template:
        check_initialized(root, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', action='store_true', help='Template repository mode: allow unfilled template placeholders')
    args = parser.parse_args(argv)
    try:
        report = run(repository(), args.template)
    except (WorkflowError, OSError, subprocess.CalledProcessError) as error:
        print(f'ai-check: {error}', file=sys.stderr)
        return 2
    for message in report.errors:
        print(f'ERROR: {message}')
    for message in report.warnings:
        print(f'WARN: {message}')
    print(f'ai-check: {len(report.errors)} error(s), {len(report.warnings)} warning(s)')
    return 1 if report.errors else 0


if __name__ == '__main__':
    sys.exit(main())
