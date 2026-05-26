# Telegram WebApp Feasibility Spike

Last updated: 2026-05-26.

## Decision

Defer a Telegram Mini App / WebApp for now. The current Telegram-native bot
flows remain useful and maintainable after the recent filters, reminders,
recaps, export, and formatting work. A WebApp should be reconsidered only when
the couple's lists and memory views become dense enough that inline keyboards
are clearly slowing normal use.

No WebApp implementation starts from this spike.

## Sources Checked

- Telegram Mini Apps documentation: <https://core.telegram.org/bots/webapps>
- Telegram Bot API `WebAppInfo`: <https://core.telegram.org/bots/api#webappinfo>
- Telegram Mini App init data validation:
  <https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app>

## Current UI Friction

The real friction is moderate, not blocking:

- Content and places filters now cover category, high rating, and recent
  activity. Combining filters still takes repeated inline-button navigation, but
  the lists are readable inside Telegram.
- Visited-place memories are compact today. They may become denser after photo
  uploads for visited places are designed.
- Reminder settings require text input for time changes, but the flow is short:
  open settings, choose morning or evening, type a time.
- Export is a single bot-delivered file, so it does not need a browser UI.
- Statistics recaps are summary pages, not dashboards that need sorting,
  charts, or drill-down controls yet.

## Candidate Flow

If a WebApp becomes worthwhile, the strongest first candidate is a read-first
Memories Explorer:

1. Launch from **Additional**, **Content**, or **Places**.
2. Verify Telegram `initData` on the server and resolve the requesting couple.
3. Show two tabs: Content and Places.
4. Offer dense controls that Telegram inline keyboards do poorly: search,
   category chips, status chips, rating range, recent/older switch, and sort.
5. Show compact cards with title, status, rating, comments count, and visited or
   completed date.
6. Return a selected item/action to the bot, while the bot remains the owner of
   mutations, notifications, and permission checks.

This keeps the WebApp as a browsing surface instead of a second product with
duplicated business rules.

## Implementation Cost

Minimum production path:

- public HTTPS hosting for the Mini App frontend;
- a small authenticated API or server-rendered page;
- Telegram `initData` validation on every request;
- couple-scoped read models for content and places;
- mobile WebView QA on iOS, Android, and Telegram Desktop;
- deployment, logs, and rollback steps for the new public surface.

Estimate:

- 1-2 days for a disposable static/read-only prototype;
- 4-7 days for a production-grade read-only Memories Explorer;
- more if editing, uploads, maps, offline states, or analytics are added.

The current VPS deployment intentionally has no public HTTP server. A WebApp
would change that operational shape and should not be added casually.

## Risks

- Privacy depends on correct Telegram init data validation and couple scoping.
- A public HTTPS surface increases deployment and monitoring work.
- Telegram WebViews differ across clients, so QA becomes broader than bot-only
  testing.
- Splitting flows between bot and WebApp can make the product feel less calm if
  the WebApp only replaces simple button flows.
- A WebApp does not remove the need for bot-side validation, notifications, or
  fallback flows.

## Recommendation

Stay Telegram-native. Revisit the WebApp option when one of these is true:

- Content or Places lists regularly exceed about 30 active or visited items per
  couple and users need search plus combined filters.
- Visited-place photo memories are implemented and need a richer gallery.
- Users ask for batch operations, map-like browsing, charts, or spreadsheet-like
  sorting that inline keyboards cannot express well.
- The deployment already has a secure public HTTPS surface for another reason.

Until then, continue improving compact Telegram flows and keep the bot fully
usable without a WebApp.
