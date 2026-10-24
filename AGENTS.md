# Repository Guidelines

{{PROJECT_NAME}}: {{PROJECT_DESCRIPTION}}

## Working Policy

- Runtime constraints and explicit user instructions take precedence. Respect the active host's plan mode; if execution is restricted, record the design and wait for authorization.
- Continue authorized work without asking between steps, and stop at the requested scope. Batch material questions, using the host's question tool when it has one. Ask before destructive actions unless that exact action is authorized, and keep a local rollback.
- Keep command output bounded (`tail`, `grep`, `head`) and read long files by section. Guidance already read in this session may be reused while unchanged; a new session loads it again. Run servers and watchers in the host's background facility, and stop the ones you started before finishing.
- Resolve the active checkout with `git rev-parse --show-toplevel` and use its own files, including in worktrees. Resolve user-supplied relative paths from the invocation directory before changing directories.
- Delegate work that needs little of the session's context and returns a compact result (independent research, bulk edits, black-box verification); keep reads and searches whose results you will reason over in the main session. Use the native `project-worker` agent for general delegated work and `project-acceptance-checker` for milestone acceptance. If a named agent is unavailable, say so and do not claim its model or effort settings. Keep architecture, integration and security decisions in the main session, and verify consequential agent claims.
- Only one agent at a time runs builds or tests in a checkout. Read-only work and light static checks may run concurrently.
- Use the configured Git identity. Never add generated-by lines, AI co-authors or AI/session trailers to commits or PRs. `.githooks/commit-msg` rejects them; never bypass it with `--no-verify`.
- Links in this file are pointers, not imports: read a reference when its stated trigger applies. Before changing this file or a skill, read [AI project guidance](CONTRIBUTING.md#ai-project-guidance).

## Layout

- `.agents/skills/` holds the project skills (`.claude/skills` is a symlink to it). `.claude/agents/` and `.codex/agents/` hold the native agent settings. [docs/AI_SETUP.md](docs/AI_SETUP.md) explains the setup and its troubleshooting.
- `tools/` holds the workflow helpers; `tools/project.toml` defines the project's check scopes.
- `PLAN.md` (roadmap) and `ISSUES.md` (unresolved issues) share stable IDs; `docs/plans/` holds execution plans and `docs/validation/` durable evidence.

## Commands

- `python3 tools/project-context.py [<milestone-id>]`: bounded roadmap context.
- `python3 tools/project-check.py --base <base> [--run]`: plan or run the checks for changed scopes.
- `python3 tools/ai-check.py`: check the AI setup (symlink, skills, agents, guidance size).
- `python3 tools/check-doc-links.py --changed`: check local Markdown links.
- `tools/project-land.sh <branch>`: guarded landing preview; `python3 tools/project-run.py --list`: unattended milestone candidates. Details: [Workflow helpers](CONTRIBUTING.md#workflow-helpers).
{{PROJECT_COMMANDS}}

## Code Style

- Match the surrounding code's naming, comments and idiom. Prefer guard clauses over long `else if` chains.
- Keep files focused; split modules that grow past a few hundred lines.

## Testing

- Start with checks relevant to the change; `tools/project-check.py` maps changed paths to the scope commands in `tools/project.toml`. A changed path that matches no scope needs manual validation, never an assumed pass.
- Turn each confirmed bug into a regression test. Do not loosen an assertion or allowlist entry to make a check pass.
- Report passed, failed, skipped and unrun checks separately.

## Documentation

- When a change affects user-visible behavior, commands, configuration or developer workflows, update the relevant documentation in the same task.
- Correct existing guidance instead of adding duplicate instructions.
- Write docs, skills and guidance in the [plain style](CONTRIBUTING.md#writing-style).

## Milestones

Use project-next-milestone for one explicitly selected or previously authorized milestone, and project-finish-milestone to close out implemented work (checks, review, independent acceptance check, fixes, simplification, commit). Without the skills, do those steps directly and report any missing independent check. For a small independent fix, run the relevant checks, review the diff, update the `ISSUES.md` and `PLAN.md` entries it affects, and commit them together.

## Commits and PRs

- Use descriptive prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Work on a branch per feature or audit pass, not on `{{MAIN_BRANCH}}`. When all of a feature's milestones are done, land the branch following [Landing a branch](CONTRIBUTING.md#landing-a-branch).
- One commit per milestone or independent fix. Fold corrections into an unpushed commit (`git commit --amend`) instead of adding a new one. Commit `PLAN.md` and `ISSUES.md` updates with the change they describe.

## Planning Files

- For roadmap work, read Portfolio/Progress, then only the selected milestone and its linked issues (`tools/project-context.py <id>`); unrelated changes need neither file. Follow [the lifecycle rules](docs/PROJECT_MANAGEMENT.md) for selection, issues, execution plans, checkpoints, completion and handoff. Proposed priorities do not approve work, and done means verified acceptance.
- Record every confirmed finding left unfixed in `ISSUES.md` in the same task. Check its [Recurring problems](ISSUES.md#recurring-problems) section before debugging environment or tool symptoms.

## Compaction

When compacting, preserve the checkpoint path and state, the current milestone, sub-step and next action, modified files, blockers, exact failing checks, and discoveries or user answers not yet written to a file. Prefer a fresh session from a persisted checkpoint over repeated compaction ([session boundaries](docs/PROJECT_MANAGEMENT.md#session-boundaries)).
