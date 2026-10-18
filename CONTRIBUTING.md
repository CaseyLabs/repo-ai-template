# Contributing to {{PROJECT_NAME}}

## Workflow

- Keep changes focused and explain their purpose.
- Base changes on `{{MAIN_BRANCH}}` unless the task names another target.
- Describe the behavior change, related issues, checks performed and known limits.
- Use prefixed commit messages: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Enable the commit hook once per clone: `git config core.hooksPath .githooks`.

## AI project guidance

Shared policy lives in `AGENTS.md`, and `CLAUDE.md` imports it. Both hosts load `AGENTS.md` in full every session, so keep it to rules that must always hold. Move task-specific procedures to the doc that owns them and leave a one-line trigger and link. Don't add `@` imports for them to `CLAUDE.md`: imports load eagerly and save nothing.

Edit skills and their resources in `.agents/skills/`. The relative symlink `.claude/skills -> ../.agents/skills` exposes the same files to Claude Code. Start either CLI normally from the checkout: Claude uses `/skill-name`, Codex uses `$skill-name` or `/skills`. Keep shared workflows free of host-specific tools and preprocessing, and keep shared `SKILL.md` frontmatter to the portable keys listed in [the AI setup](docs/AI_SETUP.md#design).

Native model and effort settings live in `.claude/agents/` and `.codex/agents/`; both read the same instructions files in `.agents/skills/project-finish-milestone/references/`. Keep the [model routing table](docs/AI_SETUP.md#model-routing) in step with them. Start a fresh session to load changed agent definitions.

Maintain the guidance like code. Add a rule only after an agent got something wrong without it, and phrase it as a check the agent can act on. Delete rules agents already follow unprompted. A rule that must never be broken belongs in a hook, deny rule or CI check, not in more emphatic wording. When an agent repeats a mistake despite a rule, the rule is probably unclear or lost in a long file: rewrite or shorten it. Claude Code's `/doctor` proposes cuts for content derivable from the code.

Validate AI-setup changes with `python3 tools/ai-check.py`. It also runs in CI and in the `tooling` check scope.

## Landing a branch

When all of a feature's milestones are done or an audit pass is complete, land the branch without being asked. Checks must pass and nothing may be uncommitted. `tools/project-land.sh` automates these steps with extra safeguards (see [Workflow helpers](#workflow-helpers)).

1. If `{{MAIN_BRANCH}}` has commits the branch lacks, rebase the branch onto it and rerun the relevant checks. On conflicts, run `git rebase --abort`, stop, and report the conflicting files.
2. Run `git switch {{MAIN_BRANCH}}` and `git merge --squash <branch>`, then commit once, listing each change the branch made in the commit body.
3. After the squash commit succeeds, push `{{MAIN_BRANCH}}` to its configured upstream.
4. Run `git branch -D <branch>` only after `git diff {{MAIN_BRANCH}} <branch>` prints nothing.

## Workflow helpers

These standard-library helpers (Python 3.11 or later) replace repeated shell recipes and keep returned output small. They keep the lifecycle and authorization rules: only the [unattended runner](#unattended-milestone-runs) selects milestones, and none of them performs review, authorizes live work or marks acceptance complete.

From the checkout root:

```bash
python3 tools/project-context.py                  # Portfolio/Progress and Git facts
python3 tools/project-context.py CORE-1            # Selected milestone, linked issues and checkpoint
python3 tools/check-doc-links.py --changed        # Changed Markdown (--all for every tracked file)
python3 tools/project-check.py --base main        # Check plan only
python3 tools/project-check.py --base main --run  # Serial checks with private logs and evidence
python3 tools/ai-check.py                         # AI setup self-check
tools/check-commit-messages.sh main..HEAD          # Rerun the commit hook on branch commits (CI does this)
```

`project-context.py` accepts `--plan`/`--issues`, `--json` and `--max-lines`. User-supplied paths resolve from the invocation directory. A missing or ambiguous milestone or plan is an error. Context reports proposed or deferred status without authorizing it.

`check-doc-links.py` checks local link targets and anchors in Markdown; it does not fetch external sites. It accepts explicit paths, `--changed`, `--all`, `--base`, `--json`, `--max-errors` and `--json-output`.

`project-check.py` maps changed paths (against the merge base of `--base` and `HEAD`) to the scopes in `tools/project.toml`. Each scope lists path globs (`*`, `?`, `**`) and the commands that check it: argv lists (no shell) or `{name, argv, cwd}` tables, where `{base}` in an argument becomes the resolved base commit. A path may match several scopes, and their commands are combined. A changed path that matches no scope is an error: add it to a scope or validate it manually, never assume it passed. Add `--scope <name>` to include a scope, and `--extra-command '["cmd", "arg"]'` (argv only, run from the checkout root) for milestone-specific checks. `--run` executes serially, stops at the first failure and saves full logs and `evidence.json` in a new private directory under `~/.cache/<cache_name>-project-checks/` (or `$XDG_CACHE_HOME`); `--output-dir` chooses another directory outside the checkout. Evidence is bound to a fingerprint of the source content, so editing any source invalidates it while committing identical content doesn't. Only one helper check or landing may run in a checkout at a time.

For the standard authorized squash landing, commit all milestone files, complete review and acceptance, and preview:

```bash
tools/project-land.sh feature-branch --evidence /absolute/path/evidence.json
# Supply a reviewed title and body file; --execute performs the authorized action.
tools/project-land.sh feature-branch --evidence /absolute/path/evidence.json \
  --title 'feat: describe the completed work' --body-file /absolute/path/body.txt --execute
```

Landing requires a clean checkout, evidence that matches the current source and covers every changed scope from the landing merge base, and a configured upstream for the main branch. It keeps `recovery/project-land-...` branches, rebases when needed and reruns the recorded checks, aborts on conflicts, respects hooks, pushes without force, and deletes the feature branch only after an equal-tree comparison. On failure it reports the retained Git state; fix the stated problem without bypassing safeguards.

Validate helper changes with `python3 -m unittest discover -s tools/tests -p 'test_*.py'` and `python3 .agents/skills/project-next-milestone/tests/paths.py`. The tests use disposable repositories, remotes and fake commands only.

### Unattended milestone runs

`tools/project-run.py` works through roadmap milestones without a user. Each milestone gets a fresh headless Claude Code (`claude -p`) or Codex (`--agent codex`) session (default: `[runner] default_agent`) running `project-next-milestone`, including its finish step and one local commit. Run it from a clean feature-branch checkout (or a clean main branch with `--land`):

```bash
python3 tools/project-run.py --list                  # Ranked eligible milestones; runs nothing
python3 tools/project-run.py                         # Best eligible milestone, then the next, ...
python3 tools/project-run.py --milestones CORE-2 --max-milestones 1
python3 tools/project-run.py --agent codex --verify-command 'make test'
python3 tools/project-run.py --land                  # Also check and land each completed milestone
```

**Selection.** Without `--milestones`, the runner rereads `PLAN.md` before each milestone and picks the best eligible one: `active` first (resuming interrupted work), then `proposed`, then lower `P` priority, then plan order. A milestone is eligible only when its project isn't `blocked`, `deferred` or `done` and every milestone ID under its **Dependencies / gates** (links, bare IDs and ranges such as `CORE-1–3`) is `done`. `--milestones` runs the listed IDs in order and accepts only `active` or `proposed` ones.

**Authorization.** Starting the runner authorizes each selected milestone's local scope, one session at a time; the session records that authorization in its checkpoint. It never reopens deferred work and never permits live external services, credential changes, data migrations, dependency upgrades, pushing or landing; sessions leave those steps unrun and recorded. Without `--land`, review the commits and land the branch yourself.

**Landing.** With `--land`, the runner itself (never a session) lands each completed milestone: it reruns `project-check.py --base <main> --run` for the whole branch, then calls `tools/project-land.sh <branch> --execute` with the milestone commit's subject and body. Started on the main branch, it creates `milestone/<id>` for each milestone. Starting the runner with `--land` authorizes pushing each landed milestone.

**Outcomes.** Each session returns `success` (milestone done and committed), `handoff` (checkpoint committed at a sub-step boundary; the runner continues in a fresh session, up to `--max-handoffs`) or `blocked` (blocker recorded; the runner moves to the next candidate). The runner then requires a clean tree, a new commit for success or handoff, and a `done` plan status for success, and runs `--verify-command` if given. Exit codes: 0 when nothing eligible remains or `--max-milestones` is reached; 2 for a blocked milestone, uncommitted changes, too many handoffs or failed verification; 1 for a session error or inconsistent result; 130 on Ctrl+C. Rerun to resume. On a usage limit the runner waits for the reported reset (or `--retry-minutes`) and resumes the same session, up to `--max-wait-hours`.

**Sessions.** Defaults are `--permission-mode bypassPermissions` (Claude) and `--sandbox danger-full-access` (Codex, because `workspace-write` blocks the commit), so sessions run checks without prompts; run it only in a checkout you are willing to let an agent change. Variables named in the `[runner] scrub_env_files` files (default `.env`, `.env.local`) are removed from the session environment so sessions don't inherit credentials. `--chrome` (Claude in Chrome) and `--playwright` (a pinned headless Playwright MCP server; needs `npx` and Google Chrome) default to the `[runner]` settings in `tools/project.toml`. Session logs go to a new private directory under `~/.cache/<cache_name>-project-runs/`. One runner may hold a checkout at a time.

## Development setup

{{PROJECT_SETUP}}
