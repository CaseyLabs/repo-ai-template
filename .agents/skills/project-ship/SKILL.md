---
name: project-ship
description: Commit current changes, push the branch, and create or update its pull request description. Use when the user asks to commit and push, update the PR or its description, open a draft PR, or merge a branch to main and push.
---

Ship the work in the requested mode (for example draft PR or merge), within existing authorization.

## Current state

Inspect `git status --short --branch`, `git diff --stat`, per-file diffs and `git log --oneline -5`. If the GitHub CLI is available, run `gh pr view --json number,title,isDraft,baseRefName,url`, and distinguish "no PR" from an authentication or network error.

## Steps

1. **Guardrails.** If project settings deny `git push` or `AGENTS.md` says not to push, commit locally and stop. Push only the authorized branch, and never force-push unless the user asked.
2. **Commit.** Stage only files that belong to this change and mention unrelated edits left unstaged. Follow the repository's commit style. No AI co-author trailer or generated-by line.
3. **Push** the current branch, setting its upstream if needed.
4. **PR.** If a PR exists, rewrite its description to describe the branch as it is now (summary, notable changes, testing), not as a log of review rounds. If none exists and the user asked for one, create it (as a draft if they said so) using the repository's PR template. No attribution lines.
5. **Land.** When all of a feature's milestones are done, or when asked, follow [Landing a branch](../../../CONTRIBUTING.md#landing-a-branch): get evidence with `python3 tools/project-check.py --base <main branch> --run` after the source is final, preview with `tools/project-land.sh "$branch" --evidence "$evidence"`, then add a reviewed `--title`, `--body-file` and `--execute` within existing authorization.
6. Reply with the commit hash, branch and PR URL.
