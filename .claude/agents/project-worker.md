---
name: project-worker
description: Worker for delegated multi-step tasks — research, audits, bulk edits, or command runs whose output would flood the main context. Use instead of general-purpose. Give it a self-contained brief and say what to return.
model: sonnet
effort: medium
maxTurns: 40
---

Read and follow `.agents/skills/project-finish-milestone/references/worker.md` from the active checkout (`git rev-parse --show-toplevel`). This file supplies host settings; the shared brief supplies the task behavior.
