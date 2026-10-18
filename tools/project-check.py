#!/usr/bin/env python3
"""Plan or run serial project checks, with compact logs and content-bound evidence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
from project_common import WorkflowError, changed_paths, checkout_lock, git, repository, resolve_path, tree_fingerprint
import project_config



def infer_scopes(config, paths):
    """Return the scopes matched by the changed paths and the paths no scope matches."""
    scopes, unknown = set(), []
    for name in paths:
        matched = {scope['name'] for scope in config['scopes'] if any(p.match(name) for p in scope['paths'])}
        scopes |= matched
        if not matched:
            unknown.append(name)
    return scopes, unknown


def check_whitespace(repo, base):
    """Run `git diff --check` over tracked changes and each nonignored untracked file."""
    code = subprocess.run(['git', 'diff', '--check', base, '--'], cwd=repo).returncode
    untracked = git(repo, 'ls-files', '--others', '--exclude-standard', '-z').stdout.split('\0')
    # A trailing slash marks an untracked nested repository, which has no file content to check.
    for name in (n for n in untracked if n and not n.endswith('/')):
        # --no-index exits 1 for a plain difference; higher codes are whitespace errors or failures.
        if subprocess.run(['git', 'diff', '--no-index', '--check', '--', os.devnull, name], cwd=repo).returncode > 1:
            code = code or 1
    return code


def command_plan(config, scopes, base, extra=()):
    commands = [{'name': 'whitespace', 'argv': ['python3', 'tools/project-check.py', '--whitespace-only', base], 'cwd': '.'}]
    for scope in config['scopes']:
        if scope['name'] in scopes:
            commands.extend({**command, 'argv': [arg.replace('{base}', base) for arg in command['argv']]}
                            for command in scope['commands'])
    commands.extend({'name': f'extra-{i + 1}', 'argv': argv, 'cwd': '.'} for i, argv in enumerate(extra))
    return commands


def run_checks(repo, commands, output_dir, metadata, tail_lines=6):
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    evidence = {**metadata, 'schema_version': 1, 'commands': commands, 'results': [], 'passed': False}
    evidence_file = output_dir / 'evidence.json'
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    for index, command in enumerate(commands):
        log = output_dir / f'{index + 1:02d}-{command["name"]}.log'
        start = time.monotonic()
        print(f'RUN {command["name"]}: {shlex.join(command["argv"])} (cwd={command["cwd"]})', flush=True)
        with log.open('w', encoding='utf-8') as stream:
            try:
                result = subprocess.run(command['argv'], cwd=repo / command['cwd'],
                                        stdout=stream, stderr=subprocess.STDOUT, env=environment)
                code = result.returncode
            except OSError as error:
                stream.write(str(error) + '\n')
                code = 127
        elapsed = round(time.monotonic() - start, 3)
        evidence['results'].append({'name': command['name'], 'exit_code': code, 'seconds': elapsed, 'log': str(log)})
        print(f'{"PASS" if code == 0 else "FAIL"} {command["name"]} ({elapsed}s); log={log}', flush=True)
        # Bound returned context; keep the complete diagnostic on disk.
        from collections import deque
        with log.open(errors='replace') as stream:
            for line in deque(stream, maxlen=tail_lines):
                print('  ' + line.rstrip()[:500])
        evidence_file.write_text(json.dumps(evidence, indent=2) + '\n')
        if code:
            print(f'STOP: remaining checks unrun; evidence={evidence_file}')
            return code if code > 0 else 1, evidence_file
    evidence['final_fingerprint'] = tree_fingerprint(repo)
    evidence['passed'] = evidence['final_fingerprint'] == evidence['tree_fingerprint']
    if not evidence['passed']:
        print('FAIL: checks changed source files; review the changes and rerun checks.')
    evidence_file.write_text(json.dumps(evidence, indent=2) + '\n')
    print(f'Evidence: {evidence_file}')
    return (0 if evidence['passed'] else 1), evidence_file


def parse_extra(values):
    commands = []
    for value in values:
        try:
            command = json.loads(value)
        except ValueError as error:
            raise WorkflowError('--extra-command must be a JSON argv array') from error
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x and '\0' not in x for x in command):
            raise WorkflowError('--extra-command needs a nonempty array of nonempty strings')
        commands.append(command)
    return commands


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', action='append', default=[], help='Also run this scope from tools/project.toml')
    parser.add_argument('--base', default='HEAD', help='Compare from the common ancestor with HEAD (use milestone base or main for landing evidence)')
    parser.add_argument('--run', action='store_true', help='Execute the displayed checks; default only plans them')
    parser.add_argument('--output-dir', help='New private log directory; relative to invocation cwd')
    parser.add_argument('--tail-lines', type=int, default=6)
    parser.add_argument('--extra-command', action='append', default=[], help='Additional required command as JSON argv, cwd=repo; no shell')
    parser.add_argument('--json', action='store_true', help='JSON plan (not combined with --run)')
    parser.add_argument('--whitespace-only', metavar='BASE', help='Only check whitespace in changes from BASE, untracked files included')
    args = parser.parse_args(argv)
    if args.whitespace_only:
        try:
            return check_whitespace(repository(), args.whitespace_only)
        except WorkflowError as error:
            print(f'ERROR: {error}', file=sys.stderr)
            return 1
    if args.json and args.run:
        parser.error('--json is for plans; --run already writes evidence.json')
    if not 0 <= args.tail_lines <= 30:
        parser.error('--tail-lines must be between 0 and 30')
    try:
        repo = repository()
        config = project_config.load(repo)
        bad = set(args.scope) - set(project_config.scope_names(config))
        if bad:
            raise WorkflowError('Unknown --scope (see tools/project.toml): ' + ', '.join(sorted(bad)))
        base = git(repo, 'rev-parse', '--verify', args.base + '^{commit}').stdout.strip()
        base = git(repo, 'merge-base', base, 'HEAD').stdout.strip()
        paths = changed_paths(repo, base)
        inferred, unknown = infer_scopes(config, paths)
        if unknown:
            raise WorkflowError('Unclassified changed paths; select their validation manually: ' + ', '.join(unknown[:10]))
        scopes = inferred | set(args.scope)
        commands = command_plan(config, scopes, base, parse_extra(args.extra_command))
        metadata = {'repo': str(repo), 'head': git(repo, 'rev-parse', 'HEAD').stdout.strip(),
                    'base': base, 'scopes': sorted(scopes), 'changed_paths': paths,
                    'tree_fingerprint': tree_fingerprint(repo),
                    'created_at': datetime.now(timezone.utc).isoformat()}
        if not args.run:
            report = {**metadata, 'commands': commands, 'execute': False}
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f'PLAN ONLY: {repo}; scopes={",".join(sorted(scopes)) or "whitespace"}; changed={len(paths)}')
                for command in commands:
                    print(f'  {command["name"]}: {shlex.join(command["argv"])} (cwd={command["cwd"]})')
                print('Add plan-specific checks with --extra-command; use --run to execute. Native/live cases remain separate.')
            return 0
        if args.output_dir:
            output = resolve_path(args.output_dir)
        else:
            cache = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / f'{config["cache_name"]}-project-checks'
            cache.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Reserve a unique name, then let run_checks create it exclusively.
            output = Path(tempfile.mkdtemp(prefix='run-', dir=cache))
            output.rmdir()
        if output == repo or repo in output.parents:
            raise WorkflowError('Keep check logs outside the checkout so evidence cannot alter its source fingerprint')
        with checkout_lock(repo):
            # Inputs may have changed while the user reviewed the plan.
            if tree_fingerprint(repo) != metadata['tree_fingerprint']:
                raise WorkflowError('Source changed before checks started; regenerate the plan')
            code, _ = run_checks(repo, commands, output, metadata, args.tail_lines)
        return code
    except (WorkflowError, OSError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
