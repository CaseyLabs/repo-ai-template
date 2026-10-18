---
name: project-next-milestone
description: Select or resume one authorized roadmap milestone, execute it, then verify and close it out. Use when asked to continue planned project work.
---

Implement one milestone only, then stop. Use the requested roadmap or execution-plan path, defaulting to `PLAN.md` in the invocation directory. A roadmap path alone does not authorize its proposed or deferred work.

## Start

1. Resolve the checkout (`repo=$(git rev-parse --show-toplevel)`) and the plan path from the invocation directory. Run `python3 "$repo/tools/project-context.py" --plan "$plan"` even when the plan looks absent: it reports a missing plan (a blocker to report, not a reason to invent work) and prints Portfolio/Progress plus Git facts.
2. Read [the project-management lifecycle](../../../docs/PROJECT_MANAGEMENT.md). Once the milestone is selected or already authorized, run `python3 "$repo/tools/project-context.py" "$id" --plan "$plan"` for that milestone, its linked issues and checkpoint. Follow truncation pointers and read technical references selectively.
3. If the request names no milestone and none is active or previously authorized, report eligible candidates and blockers, leading with the roadmap's **Next recommended** milestone, and obtain a selection. Never pick the first unfinished entry by file order or activate deferred work. If the request clearly selects one scope, proceed.
4. Reconcile the milestone with the current implementation; confirm prerequisites and gates, and ask about material scope changes. Create and link `docs/plans/<milestone-id>.md` only when complexity warrants it; otherwise checkpoint inline. Record the authorization, base commit and current step, map acceptance criteria to checks, then set the selected statuses to active.

## Work

Search for an existing implementation before adding code. Complete each sub-step without stubs or fake returns. Update the checkpoint at meaningful completions, blockers, scope changes and check results, so the work can continue without chat history. Record baseline failures and confirmed deferred findings in `ISSUES.md`.

If the host reports context nearing its compaction point, hand off at a sub-step boundary under [session boundaries](../../../docs/PROJECT_MANAGEMENT.md#session-boundaries). After one compaction, hand off at the next sub-step boundary.

Ask only material questions not answered by recorded decisions, batched, and continue independent work meanwhile.

## Finish

Read `.agents/skills/project-finish-milestone/SKILL.md` in the active checkout and perform that workflow. Stop after its summary; any next milestone starts in a fresh session.
