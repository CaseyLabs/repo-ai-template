---
name: project-run-app
description: Start, drive, screenshot, and stop the application for manual verification. Use when asked to run the app or check it running.
---

{{RUN_APP_SUMMARY}}

## Prerequisites

Run commands from the checkout root (`git rev-parse --show-toplevel`). Check required tools with `command -v`, and install locked dependencies only when that is authorized.

## Safeguards

- Use fake or disposable data. Never send, delete or modify real accounts, services or user data.
- Record whether this task started the app; never stop a session the task didn't start.
- Capture any persisted settings before changing them and restore them before stopping.

## Run

{{RUN_APP_COMMANDS}}

Start long-running processes with the host's background facility, wait for readiness with a bounded poll, and read logs by excerpt. For task-specific procedures, add files under `references/` and link each here with its trigger.

## Cleanup and report

Restore saved state, stop only the processes this task started, and inspect the final diff. Report what you checked, screenshots taken, and checks you couldn't perform.
