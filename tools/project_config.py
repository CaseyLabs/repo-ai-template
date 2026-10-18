"""Load tools/project.toml: project identity, check scopes and runner defaults."""
from pathlib import Path, PurePosixPath
import re
import tomllib

from project_common import WorkflowError

CONFIG_PATH = 'tools/project.toml'
NAME = re.compile(r'[a-z0-9][a-z0-9-]*')


def glob_regex(pattern):
    """Translate a repository glob (`**`, `*`, `?`) into an anchored regex."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith('**/', i):
            out.append('(?:.*/)?')
            i += 3
        elif pattern.startswith('**', i):
            out.append('.*')
            i += 2
        elif pattern[i] == '*':
            out.append('[^/]*')
            i += 1
        elif pattern[i] == '?':
            out.append('[^/]')
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile(''.join(out) + r'\Z')


def _string_list(value, where):
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x and '\0' not in x for x in value):
        raise WorkflowError(f'{CONFIG_PATH}: {where} must be a nonempty list of nonempty strings')
    return value


def _command(scope, index, count, value):
    default = scope if count == 1 else f'{scope}-{index + 1}'
    if isinstance(value, list):
        return {'name': default, 'argv': _string_list(value, f'scope {scope} command'), 'cwd': '.'}
    if not isinstance(value, dict) or set(value) - {'name', 'argv', 'cwd'}:
        raise WorkflowError(f'{CONFIG_PATH}: scope {scope} commands are argv lists or {{name, argv, cwd}} tables')
    name = value.get('name', default)
    cwd = value.get('cwd', '.')
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise WorkflowError(f'{CONFIG_PATH}: invalid command name in scope {scope}')
    path = PurePosixPath(cwd) if isinstance(cwd, str) else None
    if path is None or path.is_absolute() or '..' in path.parts or '\\' in cwd:
        raise WorkflowError(f'{CONFIG_PATH}: scope {scope} cwd must be a relative path inside the repository')
    return {'name': name, 'argv': _string_list(value.get('argv'), f'scope {scope} command argv'), 'cwd': str(path)}


def load(repo):
    path = Path(repo) / CONFIG_PATH
    try:
        data = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise WorkflowError(f'Cannot read {CONFIG_PATH}: {error}') from error
    project = data.get('project', {})
    cache_name = project.get('cache_name', '')
    if not isinstance(cache_name, str) or not NAME.fullmatch(cache_name):
        raise WorkflowError(f'{CONFIG_PATH}: project.cache_name must match [a-z0-9-]+')
    main_branch = project.get('main_branch', 'main')
    if not isinstance(main_branch, str) or not main_branch or main_branch.startswith('-'):
        raise WorkflowError(f'{CONFIG_PATH}: invalid project.main_branch')
    scopes, names = [], set()
    for entry in data.get('scopes', []):
        name = entry.get('name') if isinstance(entry, dict) else None
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names or name == 'whitespace':
            raise WorkflowError(f'{CONFIG_PATH}: every scope needs a unique lowercase name other than "whitespace"')
        names.add(name)
        raw = entry.get('commands', [])
        if not isinstance(raw, list):
            raise WorkflowError(f'{CONFIG_PATH}: scope {name} commands must be a list')
        commands = [_command(name, i, len(raw), value) for i, value in enumerate(raw)]
        scopes.append({'name': name, 'paths': [glob_regex(p) for p in _string_list(entry.get('paths'), f'scope {name} paths')],
                       'commands': commands})
    runner = data.get('runner', {})
    scrub = runner.get('scrub_env_files', ['.env', '.env.local'])
    if not isinstance(scrub, list) or not all(isinstance(x, str) for x in scrub):
        raise WorkflowError(f'{CONFIG_PATH}: runner.scrub_env_files must be a list of paths')
    return {
        'name': project.get('name', cache_name),
        'main_branch': main_branch,
        'cache_name': cache_name,
        'scopes': scopes,
        'runner': {
            'default_agent': runner.get('default_agent', 'claude'),
            'scrub_env_files': scrub,
            'playwright': bool(runner.get('playwright', False)),
            'chrome': bool(runner.get('chrome', False)),
            'verify_command': runner.get('verify_command', ''),
        },
    }


def scope_names(config):
    return [scope['name'] for scope in config['scopes']]
