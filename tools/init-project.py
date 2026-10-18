#!/usr/bin/env python3
"""Initialize a project created from repo-ai-template: fill placeholders, write check scopes, remove template files.

Refuses a dirty checkout or one that is already initialized. Every file is rendered before
anything is written, and the result is checked with tools/ai-check.py. This script, TEMPLATE.md
and the template's own init tests are removed, since they only apply to the template.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_common import WorkflowError, git, repository  # noqa: E402

TEMPLATE_ONLY = ['TEMPLATE.md', 'tools/init-project.py', 'tools/tests/test_init.py']
RUN_APP = '.agents/skills/project-run-app'
SLUG = re.compile(r'[a-z0-9][a-z0-9-]*')


def placeholder(key):
    return '{{' + key + '}}'


def parse_scope(value, taken):
    name, sep1, rest = value.partition(':')
    globs, sep2, command = rest.partition(':')
    if not (sep1 and sep2) or not SLUG.fullmatch(name) or name in taken or name == 'whitespace':
        raise WorkflowError(f'--scope {value!r}: use NAME:GLOBS:COMMAND with a new lowercase NAME')
    paths = [g.strip() for g in globs.split(',') if g.strip()]
    argv = shlex.split(command)
    if not paths or not argv:
        raise WorkflowError(f'--scope {value!r}: needs at least one glob and a command')
    return {'name': name, 'paths': paths, 'commands': [argv]}


def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # JSON string escapes are valid TOML basic strings.
    if isinstance(value, list):
        return '[' + ', '.join(toml_value(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{ ' + ', '.join(f'{k} = {toml_value(v)}' for k, v in value.items()) + ' }'
    raise WorkflowError(f'Cannot write {type(value).__name__} to TOML')


def render_config(original, config):
    header = []
    for line in original.splitlines():
        if line.startswith('['):
            break
        header.append(line)
    out = ['\n'.join(header).rstrip(), '', '[project]']
    out += [f'{k} = {toml_value(v)}' for k, v in config['project'].items()]
    for scope in config['scopes']:
        out += ['', '[[scopes]]', f'name = {toml_value(scope["name"])}', f'paths = {toml_value(scope["paths"])}', 'commands = [']
        out += [f'  {toml_value(command)},' for command in scope['commands']]
        out.append(']')
    out += ['', '[runner]'] + [f'{k} = {toml_value(v)}' for k, v in config['runner'].items()]
    return '\n'.join(out).lstrip('\n') + '\n'


def command_text(command):
    return shlex.join(command['argv'] if isinstance(command, dict) else command)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--name', required=True, help='Project name, as shown in documents')
    parser.add_argument('--slug', required=True, help='Lowercase identifier for caches and logs, e.g. my-project')
    parser.add_argument('--description', required=True, help='One-line project description')
    parser.add_argument('--main-branch', default='main')
    parser.add_argument('--scope', action='append', default=[], metavar='NAME:GLOBS:COMMAND',
                        help='Add a check scope: comma-separated globs and a command (split like a shell, no shell run)')
    parser.add_argument('--setup', help='Development setup command, documented in CONTRIBUTING.md')
    parser.add_argument('--keep-run-app', metavar='NAME', help='Keep the run-app skill stub as run-NAME')
    args = parser.parse_args(argv)
    try:
        root = repository()
        if not (root / 'TEMPLATE.md').is_file():
            raise WorkflowError('This checkout is already initialized (no TEMPLATE.md); edit tools/project.toml and the docs directly')
        if git(root, 'status', '--porcelain').stdout:
            raise WorkflowError('Commit or stash changes first, so the initialization diff can be reviewed on its own')
        if not SLUG.fullmatch(args.slug):
            raise WorkflowError('--slug must be lowercase letters, digits and hyphens')
        if not args.main_branch or args.main_branch.startswith('-') or \
                git(root, 'check-ref-format', '--branch', args.main_branch, check=False).returncode:
            raise WorkflowError('Invalid --main-branch')
        run_app = None
        if args.keep_run_app:
            run_app = 'run-' + args.keep_run_app
            if not SLUG.fullmatch(args.keep_run_app) or (root / '.agents/skills' / run_app).exists():
                raise WorkflowError('--keep-run-app needs a new lowercase name')

        config_path = root / 'tools/project.toml'
        original = config_path.read_text(encoding='utf-8')
        config = tomllib.loads(original)
        config['project'] = {'name': args.name, 'main_branch': args.main_branch, 'cache_name': args.slug}
        taken = {s['name'] for s in config['scopes']}
        first_added = len(config['scopes'])
        for value in args.scope:
            scope = parse_scope(value, taken)
            taken.add(scope['name'])
            config['scopes'].append(scope)
        for scope in config['scopes']:
            for command in scope['commands']:
                argv_list = command['argv'] if isinstance(command, dict) else command
                argv_list[:] = [a for a in argv_list if not (a == '--template' and 'tools/ai-check.py' in argv_list)]
        commands = [f'- `{command_text(c)}`: checks the `{s["name"]}` scope ({", ".join(f"`{p}`" for p in s["paths"])}).'
                    for s in config['scopes'][first_added:] for c in s['commands']]
        values = {
            'PROJECT_NAME': args.name,
            'PROJECT_SLUG': args.slug,
            'PROJECT_DESCRIPTION': args.description,
            'PROJECT_COMMANDS': '\n'.join(commands),
            'MAIN_BRANCH': args.main_branch,
            'PROJECT_SETUP': f'```bash\n{args.setup}\n```' if args.setup else 'Document the development setup commands here.',
            'RUN_APP_SUMMARY': f'Run {args.name} locally for manual verification.',
            'RUN_APP_COMMANDS': 'Document the start, readiness check, screenshot and stop commands here.',
        }

        # Render everything first, so an error leaves the checkout untouched.
        writes = {config_path: render_config(original, config)}
        tracked = [p for p in git(root, 'ls-files', '-z').stdout.split('\0') if p and p not in TEMPLATE_ONLY]
        for name in tracked:
            path = root / name
            if path.is_symlink() or not path.is_file() or (not run_app and name.startswith(RUN_APP + '/')):
                continue
            try:
                text = writes.get(path) or path.read_text(encoding='utf-8')
            except UnicodeError:
                continue
            new = text
            for key, value in values.items():
                if key == 'PROJECT_COMMANDS' and not value:
                    new = new.replace(placeholder(key) + '\n', '')
                new = new.replace(placeholder(key), value)
            if name == '.github/workflows/ci.yml':
                new = new.replace('        # Template mode allows unfilled placeholders; init-project.py removes the flag.\n', '')
                new = new.replace('tools/ai-check.py --template', 'tools/ai-check.py')
            if run_app and name == f'{RUN_APP}/SKILL.md':
                new = new.replace('name: project-run-app', f'name: {run_app}', 1)
            if new != text:
                writes[path] = new
        tomllib.loads(writes[config_path])  # The rendered config must parse.

        for path, text in writes.items():
            path.write_text(text, encoding='utf-8')
        if run_app:
            git(root, 'mv', RUN_APP, f'.agents/skills/{run_app}')
        else:
            git(root, 'rm', '-rq', RUN_APP)
        git(root, 'rm', '-q', '--', *[p for p in TEMPLATE_ONLY if (root / p).exists()])
        shutil.rmtree(root / 'tools/__pycache__', ignore_errors=True)
        git(root, 'config', 'core.hooksPath', '.githooks')
        print(f'Initialized {args.name}; review `git status` and `git diff`, then commit.')
        return subprocess.run([sys.executable, str(root / 'tools/ai-check.py')], cwd=root).returncode
    except (WorkflowError, OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        print(f'init-project: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
