# Mately Roadmap

Last updated: 2026-05-25.

This roadmap is derived from the current repository state, product docs, and test coverage. `tasks.json` is the TaskOS source of truth; `docs/kanban.md` and `docs/task-board.html` are generated from it.

## Current State

Mately already has a working MVP foundation:

- Couple onboarding with invite codes.
- Telegram-native main menu, recovery commands, and chat cleanup.
- Partner display names.
- Household tasks with assignment, pool tasks, recurrence, and history.
- Shared shopping list with local-midnight cleanup.
- Content tracker with completion, ratings, reactions, comments, and filters.
- Places tracker with planned/visited lists, ratings, and comments.
- Weekly and monthly statistics.
- APScheduler reminders, recaps, and recurrence jobs.
- Local cat assets and optional AI cozy suffixes with fallbacks.
- Docker Compose, Alembic migrations, and 99 passing tests.
- TaskOS planning loop.

## Ranked User Requests

Current importance order:

1. `MAT-101` / `MAT-102` - put the bot on a server so it works when local Docker is off.
2. `MAT-109` / `MAT-112` - normalize multi-couple data isolation for several couples in parallel.
3. `MAT-113` - normalize notification rules across all blocks; ask the user for block-by-block logic when this task starts.
4. `MAT-114` - add 09:00 cleanup of stale bot messages plus morning unfinished-task digest.
5. `MAT-115` - fix Statistics period buttons so the current period is not shown as a redundant button.
6. `MAT-116` - use the selected Content/Place category in add button text.
7. `MAT-117` - add a Not acquainted response for partner ratings without score/reaction/comment.
8. `MAT-118` - remove Filter from the Content menu.
9. `MAT-120` - design the Amplitude analytics event dataset and event catalog table.

Additional UX feedback from live testing:

- `MAT-121` - bold the partner invite code.
- `MAT-122` - prompt the couple creator to name the joined partner.
- `MAT-123` - render task text as Quote.
- `MAT-124` - render content and place titles as Spoiler.
- `MAT-125` - allow deleting completed-task notifications together with the related assignment info message.
- `MAT-126` - connect a production-grade AI messaging layer because the current AI behavior reads like a visible stub.

## Now

The top P0 items are:

- `MAT-103` - add reminder controls and align scheduled notifications with `docs/notification-matrix.md`.
- `MAT-114` - implement 09:00 cleanup and the morning digest from `docs/notification-matrix.md`.

## Next

After the P0 decisions are clear, the highest-value product improvements are:

- `MAT-114` - morning cleanup and task digest.
- `MAT-115` - Statistics period button fix.
- `MAT-116` - selected-category add button labels.
- `MAT-117` - Not acquainted response for content and places.
- `MAT-118` - simplified Content menu without Filter.
- `MAT-121` through `MAT-125` - live-test UX polish for onboarding, task formatting, title formatting, and notification cleanup.
- `MAT-126` - production-grade AI messaging for notification tone before deeper notification polish.
- `MAT-103`, `MAT-104`, `MAT-105` - reminder controls and block-specific partner notifications, implemented from `docs/notification-matrix.md`.

## Later

Longer-term work should stay conservative:

- `MAT-119` - smart-table export for content and places.
- `MAT-127` - photo uploads for visited-place memories.
- `MAT-120` - Amplitude analytics event catalog.
- `MAT-108` - backup and export path.
- `MAT-106` - places filters and richer place memories.
- `MAT-107` - stats that include shopping and places.
- `MAT-110` - Redis or Celery decision only if APScheduler becomes insufficient.
- `MAT-111` - optional WebApp feasibility spike only if Telegram UI becomes limiting.

## How To Update

Edit `tasks.json`, then run:

```bash
taskos sync
taskos doctor
```

Do not edit `docs/kanban.md` or `docs/task-board.html` by hand.
