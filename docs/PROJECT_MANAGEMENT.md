# Git-native project management

Read this when managing roadmap work, recording issues or preparing continuation. For unrelated changes, read `AGENTS.md` and only the relevant documentation; loading the whole roadmap or register is unnecessary.

## Documents and identifiers

- `PLAN.md` is the authoritative roadmap: project objective, status and priority, ordered milestones, acceptance and validation, dependencies and issue links. Its Portfolio and Progress sections identify candidates and active work.
- `ISSUES.md` is the authoritative register of unresolved issues: one owning project per issue, original severity, proposed priority, evidence and uncertainty, dependencies and closure criteria. Cross-project relevance is a link, never a duplicate entry.
- A substantial selected milestone gets a living ExecPlan at `docs/plans/<milestone-id>.md`, linked from its roadmap entry. Simple work keeps a short checkpoint under the milestone instead.
- Technical behavior and architecture belong in the relevant `docs/` reference. Durable verification evidence and its limits belong in `docs/validation/`. Git history keeps the routine chronology.

Use immutable, unique IDs with explicit HTML anchors (`<a id="core-1"></a>`) and standard Markdown links (`[CORE-1](../PLAN.md#core-1)`), so titles can change without breaking links. Projects use a short uppercase name; milestones use `<PROJECT>-<number>`; issues use a short uppercase prefix and a number (`CO1`). Never recycle an ID after closure; check the register and Git history before allocating one.

Each issue links its project and relevant milestones; each milestone links its issues and sits under its project anchor. If work spans projects, the issue has one owner and the others link to it. An investigation may yield a new proposed milestone; it never implicitly approves implementation.

### Roadmap format

The context helper and the unattended runner parse this format, so keep the heading shapes and bold labels exactly:

```markdown
<a id="core"></a>

## CORE — Core functionality

- **Objective / outcome:** What the project achieves.
- **Status / proposed priority:** proposed / P2.
- **Issues:** [owning register section](ISSUES.md#core).

<a id="core-1"></a>

### CORE-1 — First milestone

- **Status / proposed priority:** proposed / P2. **Dependencies / gates:** none.
- **Scope / deliverable:** What changes.
- **Acceptance:** Observable criteria.
- **Validation:** Exact commands or fixtures that prove the acceptance.
- **Issues:** [CO1](ISSUES.md#co1). **Progress:** not started.
```

Issue entries use `### CO1 — Short title` under the owning project's `## CORE` section, with an `<a id="co1"></a>` anchor.

## Status, priority and eligibility

Projects and milestones use `proposed`, `active`, `blocked`, `deferred`, `done`. Issues use `open`, `active`, `blocked`, `deferred`, `resolved`. Evidence certainty is a separate attribute, not a status. `blocked` names a specific unsatisfied gate; `deferred` records a decision to wait. `proposed`/`open` permit consideration, not execution. `active` requires an explicit request or recorded prior authorization. `done`/`resolved` require proved acceptance or closure criteria, with any limits retained.

Priorities: P1 security, privacy, data integrity or consequential correctness; P2 functional follow-ups; P3 maintenance or optional investigation. Newly assigned priorities are recommendations, not owner decisions. Keep severity independent of priority. Dependencies override priority: order prerequisites first, then higher priorities among independent work, and do not invent dependencies from thematic grouping. List external gates separately from milestone prerequisites.

A candidate is eligible for selection when its known prerequisites permit its scope. It becomes executable only when the user's request authorizes that scope. Starting the [unattended runner](../CONTRIBUTING.md#unattended-milestone-runs) authorizes the local scope of each milestone it selects, one at a time; it never reopens deferred work or waives an external gate. Deferred work requires explicit reopening. Outside such a run, if candidates differ materially in scope, present them and obtain a selection instead of implementing the first unfinished entry.

## Lifecycle

### Add an issue

Search the relevant register section for duplicates. Assign a stable unused ID, attach it to an existing project (or justify a small new one), and link a relevant milestone in both directions. Record the problem, affected symbols, impact, original severity (or unspecified), recommended priority, status, evidence and date, verification limits, reproduction if known, dependencies and closure criteria. Record confirmed findings left unfixed in the same task. Unverified reports stay labeled as such. Adding an entry does not authorize a fix.

### Recurring problems

The `ISSUES.md` Recurring problems section records environment and tool symptoms with their workaround and an occurrence count. Check it before debugging. On a second occurrence, or a costly first one, move the workaround into the applicable guidance and delete the tally.

### Start or resume one milestone

Check Git status and preserve unrelated work. Read Portfolio/Progress, the selected milestone and its linked issues only. Reconcile scope with the current implementation and dated evidence, and ask about material scope changes. Confirm prerequisites, gates and the mapping from acceptance criteria to checks. Record the authorization and any exclusions, and change only the selected statuses to active. Selecting adjacent local work does not waive a blocked gate.

Create an ExecPlan only for sufficiently complex work. It contains:

- Goal, scope and exclusions, project/milestone/issue links and authorization.
- The repository context, symbols and approach a fresh agent cannot infer.
- Dependencies, risks and concrete steps as checkboxes under `## Progress`.
- Acceptance criteria mapped to exact commands, fixtures, expected outcomes and external gates, ending with an end-to-end check that exercises the deliverable the way a user would.
- Living sections: `## Surprises & Discoveries`, `## Decision Log`, `## Outcomes & Retrospective`.
- A checkpoint: branch and base revision, current step, next concrete action, changed files, remaining work, exact command results, unrun checks and blockers.

An ExecPlan must support continuation without chat history. Link it from the roadmap; the roadmap status stays authoritative and the detailed progress stays in the plan. Small tasks record the same checkpoint facts inline.

### Implement and checkpoint

Update the active checkpoint at meaningful completions, discoveries, blockers, scope changes and before handoff or compaction. Update issue evidence when facts change. Run proportionate checks and distinguish failed, passed and unrun results. Do not claim live or production compatibility from local fixtures. The roadmap grants no permission for live services, credentials, data migrations, external accounts or dependency upgrades; those need explicit authorization.

### Session boundaries

Run one milestone per session, and start the next one in a fresh session from the committed roadmap and checkpoint. When the host reports context nearing its compaction point (Claude Code `/context`, Codex `/status`), finish the current sub-step, checkpoint everything the remaining work needs, and use project-handoff. A session that has already been compacted once hands off at the next sub-step boundary instead of continuing into a second compaction. Automatic compaction stays enabled as a fallback; the checkpoint, not the summary, is the continuation state.

### Complete and stop

Use project-finish-milestone for checks, independent acceptance review, correctness fixes and behavior-preserving simplification. Mark done only when acceptance is proved; outstanding required checks keep the work active or blocked. Resolve only issues that were actually fixed and verified.

Move lasting behavior and decisions to technical docs and evidence to validation records. Collapse completed roadmap detail to a short ID, status and evidence link while it is still referenced, and remove resolved register entries once nothing links to them (keep or update anchors first). Commits, pushes and landing follow repository policy, and a no-commit request always wins. Completing one milestone never authorizes the next.

After completing a milestone, record the next recommended milestone in roadmap Progress as one line, `**Next recommended:** [ID](#id) — reason`, replacing any earlier one. If nothing is eligible, name the best issue to turn into a milestone or what would unblock work. A recommendation is not authorization.

### No active milestone / handoff

State "No active milestone" in roadmap Progress, keep the **Next recommended** line current, and list candidates and blockers without changing their statuses. A handoff names the IDs, roadmap section, checkpoint path, checkout/branch/revision/dirty state, next authorized action, results and limits, and commit/push status. If no work is authorized, the next action is selection or blocker resolution.

## Basis

Adapted from the [OpenAI ExecPlan recipe](https://developers.openai.com/cookbook/articles/codex_exec_plans) (living, restartable, outcome-focused plans), Codex [best practices](https://learn.chatgpt.com/guides/best-practices) and Claude Code [best practices](https://code.claude.com/docs/en/best-practices) (one coherent unit of work per session; fresh sessions from precise prompts). Claude Code re-injects `CLAUDE.md` and invoked skills after [compaction](https://code.claude.com/docs/en/context-window), but conversation-only state is summarized, so it must be checkpointed.
