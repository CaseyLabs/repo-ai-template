# repo-ai-template

A starting point for new repositories that are worked on with both Claude Code and Codex CLI. It provides one shared policy file, portable skills, paired native agent files, Git-native planning (roadmap, issue register, checkpoints, handoffs) and standard-library helpers for checks, landing and unattended milestone runs. [docs/AI_SETUP.md](docs/AI_SETUP.md) explains the design.

`tools/init-project.py` deletes this file, itself and its tests (`tools/tests/test_init.py`) when it initializes a project; on an initialized checkout it refuses to run.

## Start a project

1. Create a repository from this template (GitHub **Use this template**, or `git clone` and reset the remote), and clone it with symlinks enabled (`git -c core.symlinks=true clone <url>` on Windows).
2. Run the init script from the clean checkout:

   ```bash
   python3 tools/init-project.py --name "My Project" --slug my-project \
     --description "One-line description." \
     --scope 'code:src/**,tests/**:make test' --setup 'make setup'
   ```

   `--scope NAME:GLOBS:COMMAND` adds a check scope (comma-separated globs; the command is split like a shell command, without running a shell). Repeat it for each scope. `--main-branch` defaults to `main`. `--keep-run-app NAME` keeps the `project-run-app` skill stub renamed to `run-NAME`; without it the stub is removed. The script also renames the project in `tools/project.toml` (keeping the `docs` and `tooling` scopes), drops `--template` from the `ai-check` runs, sets `core.hooksPath` and finishes with `tools/ai-check.py`.
3. Review the diff, fill in the `## Code Style` and `## Testing` sections of `AGENTS.md` with project rules, and commit.
4. Trust the checkout in Codex so its project agents load ([troubleshooting](docs/AI_SETUP.md#troubleshooting)).
5. If your personal skills or agents duplicate the `project-` ones, hide the duplicates in the checkout's `.claude/settings.local.json` ([troubleshooting](docs/AI_SETUP.md#troubleshooting)).

## Maintain the template

- Placeholders use `{{UPPER_CASE}}`. `python3 tools/ai-check.py --template` allows them; in an initialized project they are errors.
- Keep the template project-neutral: no language, framework or product assumptions outside `tools/project.toml` scopes and placeholders.
- Run `python3 -m unittest discover -s tools/tests -p 'test_*.py'`, `python3 .agents/skills/project-next-milestone/tests/paths.py` and `python3 tools/ai-check.py --template` before committing.
- When host behavior changes, update [docs/AI_SETUP.md](docs/AI_SETUP.md) (the references carry a review date) and the agent files together; the `project-review-ai-setup` skill checks for such changes on demand.
- Proposed, not started: a small guidance eval set (about 10 golden tasks run through headless `tools/project-run.py` sessions, each run more than once) graded on whether the right skill triggered, the acceptance checker caught a planted failure, and the final reply met a rubric. Use it to compare a guidance, skill or agent change against the baseline and keep only changes that hold up.

## Origin

Derived from the Mailven repository's AI setup (2026-10). Lessons carried over: config-driven check scopes instead of hard-coded languages; portable skill frontmatter only; a `project-` prefix on skills and agents to avoid clashes with personal ones; one model routing table that is checked; a self-check for the symlink, skills, agents and guidance size; and shorter skill text that points to the policy instead of repeating it.
