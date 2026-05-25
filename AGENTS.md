# AGENTS.md

<!-- TASKOS:START -->
## Codex TaskOS Loop

When this project uses the TaskOS implementation loop:

- Treat `tasks.json` as the source of truth for task status and dependencies.
- Run `taskos claim` before implementation changes.
- Implement exactly one claimed task.
- Use `taskos done <TASK_ID> --summary "..." --check "..."` after completion.
- Use `taskos block <TASK_ID> --reason "..."` when credentials, services, or decisions are missing.
- Use `taskos release <TASK_ID> --reason "..."` if abandoning a claim.
- Do not manually edit generated views such as `docs/kanban.md` or `docs/task-board.html`.
- Run relevant checks before marking a task done.

Canonical docs to read when relevant:

- `README.md`
- `ROADMAP.md`
- `docs/mately_description.md.txt`
- `docs/mately_step_by_step.md.txt`
<!-- TASKOS:END -->
