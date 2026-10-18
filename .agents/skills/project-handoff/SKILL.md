---
name: project-handoff
description: Prepare a repository-backed handoff for a fresh session in either host. Use when asked to hand off work or provide a next-session prompt.
---

Prepare a handoff with the user's requested focus, if any.

1. **Questions.** Check recorded decisions, then batch material open questions. Record unanswered blockers explicitly.
2. **Persist first.** Following [the lifecycle](../../../docs/PROJECT_MANAGEMENT.md), update the milestone's checkpoint (ExecPlan or inline) and roadmap summary: IDs, current step, changed files, remaining work, decisions, exact check results and unrun checks, authorization limits, branch, pre-commit base revision, and dirty work that must remain. With no active work, report candidates and gates without changing statuses. Work outside the roadmap uses its own task document or a short handoff document.
3. **Commit.** If commits are prohibited, leave the checkpoint uncommitted and report its path. Otherwise commit only verified task changes plus the checkpoint, and list unrelated or unverified work left alone. Capture the resulting revision and `git status --short --branch`; don't make a second commit just to record the first one's hash.
4. **Prompt.** Emit one paste-ready fenced block that works in either host: checkout, branch, revision and dirty state; instruction and checkpoint paths to read; IDs, the next authorized action and what makes it done; validation evidence and unrun checks; blockers and pitfalls; permitted scope and commit/push status. For roadmap work, ask the next session to use the project-next-milestone skill with the milestone ID and checkpoint path; don't use host-specific commands in the prompt.
5. Tell the user to start a fresh session and paste the prompt.
