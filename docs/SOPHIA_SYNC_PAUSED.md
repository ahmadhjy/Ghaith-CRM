# Sophia synchronization — temporarily paused

Effective with this deployment on 16 October 2026, external WhatsApp dashboard
lead imports are disabled by default, pending investigation of status changes,
old chats, duplicate leads, and unexpected Sold orders.

## What is paused

- The PythonAnywhere scheduled `sync_sophia_leads` command exits normally with a
  “synchronization is paused” message. It makes no Sophia requests and does not
  fetch departments, write records, or create/update the sync state.
- “Sync now” shows a pause notice and a disabled button. Direct manual imports
  (including `?run=1`, agent filters, backfills, and dry runs) are blocked.
- The Sold receiver returns HTTP 503, code `SOPHIA_SYNC_PAUSED`, with
  `Retry-After: 3600`. It does not acknowledge the event as processed, write a
  lead, or create an order. Sophia may retry subject to its own retry policy;
  the CRM does not queue these events locally.
- Legacy dashboard lead/contact create, update, qualify, close-deal, follow-up,
  and notification write endpoints also return the paused response.
- Service-layer checks prevent direct calls from bypassing the pause.

Existing leads, orders, payments, agent mappings, departments, credentials, and
sync timestamps are retained. Manual CRM work and read-only API lookups remain
available. This deployment does not remove duplicates or undo previous imports.

## Deploy

```bash
cd /home/ghaithtravel/ghaithleads && BACKUP_MEDIA=no bash deploy/deploy.sh
```

There is no new database migration for the pause. Production settings.py is
preserved by deploy; if it has no `SOPHIA_SYNC_ENABLED` setting, the code defaults
to paused. Development settings also default to false.

The scheduled task can remain configured: each invocation is a no-op while
paused. Optionally disable that task in PythonAnywhere to avoid unnecessary runs.
The production web app must reload for its webhook/manual routes to pick up the
new code (the normal deployment reload handles this).

## Resume only after investigation

Do not enable synchronization yet. After validating the upstream status logic
and agreeing the desired restart window:

1. Review duplicate matching, assignment, status timestamps, and Sold order
   creation in a test database.
2. Decide whether changes accumulated during the pause should be imported.
   The watermark has not advanced: resuming with the old watermark may import
   the backlog, including old Sold chats. Do not reset it casually.
3. Explicitly set `SOPHIA_SYNC_ENABLED = True` in the settings used by both the web
   app and scheduled command, then reload. In settings that use the environment
   loader, `SOPHIA_SYNC_ENABLED=true` has the same effect. Use boolean `True` or
   `False` when editing settings.py directly.
4. Coordinate pending/retried Sold events with Sophia before re-enabling.

To pause again, set `SOPHIA_SYNC_ENABLED = False` and reload. Never delete tokens,
agent mappings, synced records, or the watermark as a way to pause.
