# AI setup

How this repository supports Claude Code and Codex CLI with one set of guidance, skills and agent instructions. Read this when changing the AI setup or diagnosing a host that doesn't load it. `python3 tools/ai-check.py` checks that the structure below is intact.

## Design

| Concern | Shared source | Claude Code | Codex CLI |
| --- | --- | --- | --- |
| Always-loaded policy | `AGENTS.md` | `CLAUDE.md` contains only `@AGENTS.md` | reads `AGENTS.md` natively |
| Skills | `.agents/skills/<name>/SKILL.md` | `.claude/skills` → `../.agents/skills` (relative symlink); `/name` | native discovery; `$name` or `/skills` |
| Agent behavior | `.agents/skills/project-finish-milestone/references/*.md` | `.claude/agents/<name>.md` sets model, effort, tools | `.codex/agents/<name>.toml` sets model, effort, sandbox |
| Hard rules | `.githooks/commit-msg`, CI | `.claude/settings.json` deny rules | sandbox and approval settings |
| Deterministic work | `tools/*.py` (Python standard library) | same | same |

Principles:

1. **One source per fact.** Policy lives once in `AGENTS.md`; procedures live in the doc or skill that owns them, linked with a one-line trigger. Host files only adapt.
2. **Small always-loaded context.** Both hosts load `AGENTS.md` in full every session, and `@` imports in `CLAUDE.md` load eagerly too, so imports save nothing. `ai-check` enforces a size budget (100 lines, 12 KiB; Codex stops reading at 32 KiB by default).
3. **Portable skills.** Shared `SKILL.md` frontmatter uses only the [Agent Skills](https://agentskills.io/specification) keys (`name`, `description`, `license`, `compatibility`, `metadata`). Host-only keys (`model`, `allowed-tools`, `context`) belong in host adapters; skills must never grant tools or permissions. Skill bodies use plain Markdown and shell commands, with no host preprocessing.
4. **Thin agent files.** Both hosts' agent files point to the same instructions file and add only host settings. Every Claude agent has a Codex counterpart with the same name (Codex may add extra roles such as `file_reader`).
5. **Namespaced names.** Project skills and agents start with `project-` so they don't collide with personal or plugin skills such as `worker` or `ship`.
6. **Enforce outside the model.** Rules that must hold (no AI attribution, no force-push) are enforced by Git hooks, CI and host deny rules, not just written down. Claude deny rules match the flag in any argument position, and `ai-check` fails if one is missing. Deny patterns can't catch every spelling (bundled flags such as `git commit -an`), so CI reruns the commit hook on every pushed or pull-request commit (`tools/check-commit-messages.sh`).
7. **State in Git, not chat.** Roadmap, issues, checkpoints and handoff prompts are files, so either host can continue the other's work ([lifecycle](PROJECT_MANAGEMENT.md)).
8. **Disclose fallbacks.** When a named agent or capability is unavailable, a workflow says so and never claims the configured model or effort was applied.

## Model routing

Update this table and the agent files together; `ai-check` compares them. Primary sessions use each user's own default model; the repository sets no session-wide model.

| Agent | Claude model | Claude effort | Codex model | Codex effort |
| --- | --- | --- | --- | --- |
| project-acceptance-checker | sonnet | low | gpt-6-luna | medium |
| project-worker | sonnet | medium | gpt-6-luna | medium |
| file_reader | - | - | gpt-6-luna | low |

A project that wants a specific model for one skill sets it in a host adapter, not in shared `SKILL.md` frontmatter. Claude-only skill keys such as `model:` fail the generic skill validator and `ai-check`.

## Troubleshooting

- **Codex reports `unknown agent_type` for `project-worker`.** Codex loads project-scoped agents only for a trusted checkout. Trust the clone through normal Codex onboarding; trust on a parent directory may not cover a nested Git checkout. Skill discovery can still work while agents don't, and a command-line `-c 'projects."<path>".trust_level="trusted"'` override did not load project agents in codex-cli 0.163.0. Do not copy agents into personal configuration to work around trust.
- **Claude doesn't list the project skills.** Check that `.claude/skills` is a symlink (`ls -l .claude/skills`), not a text file containing `../.agents/skills`. On Windows, enable Developer Mode (or symlink privileges) and clone with `git -c core.symlinks=true clone <url>`. Never replace the link with a copied tree.
- **A personal skill or agent shadows a project one.** Keep the `project-` prefix; if a personal skill duplicates a project skill's purpose, disable it per project in `.claude/settings.local.json` (`skillOverrides`), not in shared settings.
- **The commit hook doesn't run.** Run `git config core.hooksPath .githooks` (`tools/init-project.py` sets it for new projects).
- **Changed agent files have no effect.** Start a fresh session; both hosts read agent definitions at startup.

## References

Reviewed 2026-10-18 (Claude Code 2.1.301, Codex CLI 0.163.0):

- Best practices: [Claude Code](https://code.claude.com/docs/en/best-practices) and [Codex](https://learn.chatgpt.com/guides/best-practices). The setup follows both: short always-loaded guidance with on-demand skills, verification by runnable checks with evidence, an independent fresh-context acceptance review that reports only correctness and requirement gaps, plan-then-implement milestones with self-contained ExecPlans, and one unit of work per session with file-based handoff. Side-effecting skills (`project-ship`) stay model-invocable because landing is part of authorized milestone work; their guardrails are deny rules and Git hooks.
- Claude Code: [memory and `@` imports](https://code.claude.com/docs/en/memory) (imports load at launch, up to four hops; Claude Code reads `AGENTS.md` natively only when no `CLAUDE.md` exists, so the import stays), [skills](https://code.claude.com/docs/en/skills) (symlinked skill directories are supported), [subagents](https://code.claude.com/docs/en/sub-agents), [permissions](https://code.claude.com/docs/en/permissions), [headless mode](https://code.claude.com/docs/en/headless).
- Codex: [AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [skills](https://learn.chatgpt.com/docs/build-skills), [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) (project trust, agents, `project_doc_max_bytes`).
- [Agent Skills specification](https://agentskills.io/specification) and the [AGENTS.md format](https://agents.md).
