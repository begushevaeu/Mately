# Mately Analytics Event Catalog

This catalog defines the Amplitude-ready analytics dataset for Mately. It is a
design document only: events are not emitted until an analytics client is added.

## Product Questions

- Where do couples drop out of onboarding: start, invite creation, invite join, or alias setup?
- Which shared blocks become daily habits: tasks, shopping, content, places, statistics, or settings?
- Which actions create reciprocal partner activity, such as task completion, rating requests, or comments?
- Do reminders and notifications lead to useful follow-up actions or mostly get ignored?
- Which flows create errors or repeated retries that should be simplified?
- Are exports, backup-related flows, and future analytics surfaces used by real couples?

## Privacy Boundaries

Amplitude must receive only pseudonymous identifiers and low-sensitivity product metadata.

Allowed identifiers:

- `user_key`: stable HMAC or generated analytics UUID for one user.
- `couple_key`: stable HMAC or generated analytics UUID for one couple.
- `session_key`: short-lived generated UUID for one bot interaction session.

Never log:

- Bot tokens, OpenAI keys, database URLs, passwords, or environment values.
- Raw Telegram user IDs, usernames, first names, chat IDs, message IDs, or invite codes.
- User-entered task titles, shopping item names, content titles, place names, comments, alias names, or free-form message text.
- AI prompts, AI responses, notification body text, cat asset file paths, or Telegram photo/file IDs.
- Cross-couple data, row IDs that can be joined back to production tables, or unbounded error traces.

Prefer enums, booleans, counts, durations, status values, and coarse buckets. If a property could identify a person, home, exact place, secret, or message content, it does not belong in Amplitude.

## Common Properties

Every event should include these properties unless technically unavailable:

| Property | Type | Description | Privacy note |
| --- | --- | --- | --- |
| `user_key` | string | Pseudonymous actor id. | No raw Telegram id. |
| `couple_key` | string | Pseudonymous couple id. | Required for couple-scoped analysis. |
| `event_version` | int | Schema version, starts at `1`. | Safe metadata. |
| `bot_surface` | enum | `message`, `callback`, `scheduler`, `system`. | No message text. |
| `timezone` | string | Couple timezone name. | Allowed; avoid exact location data beyond timezone. |
| `is_couple_ready` | bool | Whether both partners are connected. | Safe lifecycle flag. |

## Event Table

| Event | Owner | Trigger | Properties | Privacy notes |
| --- | --- | --- | --- | --- |
| `onboarding_started` | Product | User starts or re-enters onboarding. | `entrypoint`, `has_existing_user`, `is_couple_ready` | No username or first name. |
| `invite_created` | Product | User creates a couple invite. | `invite_ttl_hours`, `creator_role` | Do not log invite code. |
| `invite_joined` | Product | Partner joins a couple through an invite. | `join_result`, `couple_age_bucket` | No invite code or raw user ids. |
| `partner_alias_prompted` | Product | Bot asks a user to configure partner display names. | `prompt_reason`, `target_role` | Do not log alias text or emoji. |
| `partner_alias_saved` | Product | Partner alias setup is completed. | `has_emoji`, `cases_count` | Do not log names or emoji value. |
| `task_created` | Product | A task is saved. | `assignment_type`, `has_deadline`, `recurrence_type` | Do not log task title. |
| `task_assigned` | Product | Task is assigned or reassigned to a partner. | `assignment_type`, `has_deadline` | No task title or user names. |
| `task_claimed` | Product | User claims an unassigned task. | `had_deadline`, `deadline_bucket` | Deadline bucket only, not exact title. |
| `task_completed` | Product | User completes a task. | `completion_source`, `deadline_state`, `age_bucket` | No task title. |
| `task_archived` | Product | Task is removed or stopped. | `previous_status`, `recurrence_type` | No task title. |
| `shopping_item_added` | Product | Shopping item is saved. | `list_size_bucket` | Do not log item name. |
| `shopping_item_bought` | Product | Shopping item is marked bought. | `age_bucket`, `list_size_bucket` | Do not log item name. |
| `shopping_cleanup_archived` | Operations | Scheduler archives bought shopping items. | `archived_count`, `job_result` | Count only. |
| `content_item_added` | Product | Content item is saved. | `content_category`, `planned_count_bucket` | Do not log title. |
| `content_completed` | Product | Content item is marked completed. | `content_category`, `age_bucket` | Do not log title. |
| `content_rating_saved` | Product | User rates completed content. | `content_category`, `score_bucket`, `has_reaction` | Reaction can be logged only as enum key, not free text. |
| `content_not_acquainted_saved` | Product | User marks content as not acquainted. | `content_category` | No title. |
| `content_comment_added` | Product | User adds a content comment. | `content_category`, `comment_length_bucket` | Never log comment text. |
| `place_item_added` | Product | Place is saved. | `place_category`, `planned_count_bucket` | Do not log place name or address. |
| `place_visited` | Product | Place is marked visited. | `place_category`, `age_bucket` | No place name. |
| `place_rating_saved` | Product | User rates a visited place. | `place_category`, `score_bucket` | No place name. |
| `place_not_acquainted_saved` | Product | User marks a place as not visited personally. | `place_category` | No place name. |
| `place_comment_added` | Product | User adds a place comment. | `place_category`, `comment_length_bucket` | Never log comment text. |
| `statistics_viewed` | Product | User opens weekly or monthly stats. | `period`, `completed_tasks_bucket`, `visited_places_bucket` | Counts and buckets only. |
| `settings_viewed` | Product | User opens settings. | `morning_enabled`, `evening_enabled`, `reminders_paused` | Safe booleans. |
| `reminder_setting_changed` | Product | User toggles or changes reminder settings. | `setting_name`, `new_state`, `time_bucket` | Log hour bucket, not full user text. |
| `notification_scheduled` | Lifecycle | Scheduler creates a due notification. | `notification_type`, `dedupe_result`, `scheduled_hour` | No notification text. |
| `notification_delivered` | Lifecycle | Notification send succeeds. | `notification_type`, `delivery_surface`, `used_photo`, `has_reply_markup` | No chat id, message id, caption, or asset path. |
| `notification_failed` | Reliability | Notification send fails. | `notification_type`, `error_category`, `retryable` | No raw exception trace or Telegram payload. |
| `notification_deduped` | Reliability | Scheduler skips already-sent notification. | `notification_type`, `dedupe_window` | No dedupe key value. |
| `block_closed` | UX | User closes a bot-managed block. | `block_name`, `message_count_bucket` | No message IDs. |
| `export_requested` | Product | User requests a future data export. | `export_type`, `format`, `row_count_bucket` | Couple-scoped only; no link secrets. |
| `export_delivered` | Product | Export is delivered to Telegram or external storage. | `export_type`, `format`, `delivery_result` | Do not log file path, URL token, or contents. |
| `backup_documentation_viewed` | Operations | Operator or admin opens backup docs, if an admin UI exists later. | `surface` | Optional future event; no server paths. |
| `bot_error_shown` | Reliability | User receives a generic error fallback. | `surface`, `error_category`, `state_name` | No stack trace or user message text. |
| `job_finished` | Reliability | Scheduled job completes. | `job_name`, `job_result`, `affected_count_bucket`, `duration_bucket` | No raw SQL, secrets, or payloads. |

## Property Buckets

- `age_bucket`: `same_day`, `1_3_days`, `4_7_days`, `8_30_days`, `over_30_days`, `unknown`.
- `deadline_bucket`: `none`, `future`, `due_today`, `overdue`.
- `score_bucket`: `1_4`, `5_7`, `8_10`.
- `comment_length_bucket`: `1_50`, `51_200`, `201_1000`.
- `list_size_bucket` and other count buckets: `0`, `1_3`, `4_10`, `11_30`, `over_30`.
- `duration_bucket`: `under_250ms`, `250ms_1s`, `1s_5s`, `over_5s`.
- `error_category`: `validation`, `telegram_api`, `database`, `ai_provider`, `scheduler`, `unknown`.

## Ingestion Plan

1. Add a small analytics service with a single `track(event_name, properties)` API.
2. Keep it optional behind environment settings such as `AMPLITUDE_API_KEY` and `ANALYTICS_ENABLED`.
3. Build `user_key` and `couple_key` from a server-side secret or stored generated analytics UUIDs, not raw IDs.
4. Send events asynchronously through a bounded in-memory queue. If the queue is full, drop analytics events and keep bot behavior moving.
5. Use short network timeouts and never fail a bot command because analytics delivery failed.
6. Validate event names and property keys against this catalog in tests.
7. Sample high-volume reliability events if needed, but never sample core product lifecycle events.

## Implementation Notes

- Start with product lifecycle events and notification delivery events; they answer the largest open questions.
- Keep schema versioning simple with `event_version`.
- Add new events to this catalog before emitting them.
- Store no analytics payloads in the application database unless a future reliability need appears.
