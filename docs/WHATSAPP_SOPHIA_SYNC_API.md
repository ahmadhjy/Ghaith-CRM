# WhatsApp (Sophia) ↔ Ghaith CRM — Lead Sync Integration Spec

**Audience:** Sophia dashboard development team.
**Status:** Draft for implementation. This document defines the contracts both sides must build.
**Scope:** Lead records only. No orders, invoices, clients, payments, or two‑way WhatsApp messaging.

This spec replaces the previous push‑only integration (`WHATSAPP_DASHBOARD_API.md`). The logic below is the new agreed behaviour.

---

## 1. Overview

Sales agents work inside the Sophia WhatsApp dashboard and **manually set each chat's status label** from a fixed list. Sophia's dashboard is the **source of truth for lead status and departments**. The CRM consumes those changes using a **hybrid sync**:

1. **Daily batch pull (CRM → Sophia).** Every day at **07:00 Asia/Beirut**, the CRM calls Sophia and asks for every chat whose status changed since the last successful sync. The CRM applies those changes.
2. **Real‑time Sold webhook (Sophia → CRM).** The moment an agent changes a chat's label to **Sold**, Sophia immediately POSTs that chat to the CRM. This does not wait for the 7am batch.

**No other event triggers a sync.** Any change other than "became Sold" is picked up only by the next 07:00 batch.

```
                 ┌───────────────────────────┐
   07:00 daily → │ CRM pulls changed chats     │ ── GET /api/crm/chats?status_changed_since=…
                 │ + department list           │ ── GET /api/crm/departments
                 └───────────────────────────┘
                 ┌───────────────────────────┐
 label = Sold  → │ Sophia pushes immediately   │ ── POST {CRM}/api/whatsapp/sync/sold/
                 └───────────────────────────┘
```

### Direction summary

| Flow | Caller | Purpose | Timing |
|------|--------|---------|--------|
| `GET /api/crm/departments` | CRM → Sophia | Sync department list | Daily (before chats) |
| `GET /api/crm/chats?status_changed_since=…` | CRM → Sophia | Pull changed leads | Daily 07:00 Asia/Beirut |
| `POST /api/whatsapp/sync/sold/` | Sophia → CRM | Immediate Sold notification | Real‑time on label = Sold |

---

## 2. Statuses (fixed list)

Sales agents must select **only** from this list. No free‑form or custom labels. Sophia sends the normalized `value`; the CRM maps it to its internal stage.

| Sophia label | `status` value (sent to CRM) | CRM internal stage | Notes |
|--------------|------------------------------|--------------------|-------|
| New (when received) | `new` | On Hold | Chat just received, no agent reply yet |
| Progress (agent replied) | `progress` | Processing | Active conversation |
| Offer Sent (follow‑up) | `offer_sent` | Negotiation / Follow‑up | Pricing/offer shared, awaiting decision |
| Sold | `sold` | Finalized — marked **sold** | **Triggers the real‑time webhook** |
| Lost | `lost` | Finalized — lost | |
| Unqualified | `unqualified` | Unqualified | |

If Sophia sends a `status` value outside this set, the CRM rejects the record with `INVALID_STATUS`.

---

## 3. Timezone & timestamp rules

- **All timestamps** in both directions must be **ISO 8601 with an explicit UTC offset**, e.g. `2026-07-31T14:05:00+03:00` or `2026-07-31T11:05:00Z`. Do not send naive/local strings without an offset.
- The daily batch runs at **07:00 Asia/Beirut** (UTC+03:00, or +02:00 if DST ever applies — always trust the offset in the string, not the wall‑clock).
- Every chat must carry a **`status_changed_at`** — the moment the current status label was last set. This is the single field the sync logic depends on.

---

## 4. Authentication

Two independent credentials, one per direction.

### 4.1 CRM → Sophia (pull)
Sophia issues a bearer token to the CRM. The CRM sends it on every request:

```http
Authorization: Bearer <SOPHIA_API_TOKEN>
```

### 4.2 Sophia → CRM (webhook)
The CRM issues a shared secret to Sophia. Sophia sends it on every webhook call:

```http
X-Webhook-Secret: <CRM_WEBHOOK_SECRET>
```

Requests with a missing/invalid credential receive `401`. Both secrets are rotatable via environment variables (no code change).

---

## 5. Departments (shared list)

Both sides already use the **same departments**. The CRM already has them seeded; Sophia's dashboard uses the same set. The pull below is only to keep the lists aligned going forward (detect renames / new departments / inactive ones) — not to invent a separate catalog.

Agreed department ids:

| `id` | Name |
|------|------|
| `reservation` | Reservation |
| `honeymoon_far_east` | Honeymoon & Far East |
| `sharm` | Sharm |
| `civil_marriage` | Civil Marriage |
| `turkey` | Turkey |

Each department needs a **stable, unique `id` that never changes** (renames of the display name are fine).

### Endpoint (Sophia builds)

```http
GET {sophia_base}/api/crm/departments/
Authorization: Bearer <SOPHIA_API_TOKEN>
```

### Response `200 OK`

```json
{
  "departments": [
    { "id": "reservation",        "name": "Reservation",           "is_active": true },
    { "id": "honeymoon_far_east", "name": "Honeymoon & Far East",  "is_active": true },
    { "id": "sharm",              "name": "Sharm",                 "is_active": true },
    { "id": "civil_marriage",     "name": "Civil Marriage",        "is_active": true },
    { "id": "turkey",             "name": "Turkey",                "is_active": true }
  ]
}
```

**CRM behaviour:** on each pull, upsert departments by `id` (create new, update names, mark missing ones inactive rather than deleting).

**Confirmed agent-based assignment (agreed with Sophia).** `assigned_agent` on a chat is a **stable agent id — the same id returned by `GET /departments` — and it never changes.** The CRM maps that id to a CRM user (each user is linked to their Sophia agent id in the Django admin), and the **lead's department is taken from that CRM user's profile**, not from the chat. So once we know the agent, we know the department. If a chat has no `assigned_agent` (or it is unknown to the CRM), the CRM falls back to the payload `department` and auto-assigns the active agent in that department with the fewest open leads.

---

## 6. Daily chat pull (CRM pulls from Sophia)

### Endpoint (Sophia builds)

```http
GET {sophia_base}/api/crm/chats/?status_changed_since=2026-07-31T07:00:00%2B03:00&page=1
Authorization: Bearer <SOPHIA_API_TOKEN>
```

- `status_changed_since` (required): ISO 8601 with offset. Return **only** chats whose `status_changed_at` is **strictly greater** than this value.
- `page` (optional): 1‑based page number for pagination.

The CRM sends the timestamp of its **last successful pull** as `status_changed_since` (the "watermark"). On the very first run it sends a historical date to backfill.

### Response `200 OK`

```json
{
  "chats": [
    {
      "external_id": "wa_84f2c9e1",
      "name": "Sara Haddad",
      "phone": "+96170123456",
      "department": "turkey",
      "status": "progress",
      "status_changed_at": "2026-07-31T14:05:00+03:00",
      "destination": "Antalya",
      "chat_summary": "Customer asked about a 7-night package in August for 2 adults.",
      "assigned_agent": null,
      "last_customer_message_at": "2026-07-31T13:59:00+03:00",
      "last_agent_action_at": "2026-07-31T14:05:00+03:00",
      "email": null
    }
  ],
  "next_page": 2
}
```

- `next_page`: the next page number, or `null` when there are no more pages.
- Results should be ordered by `status_changed_at` ascending (oldest change first) so a failed run can resume safely.

### CRM sync decision (per chat)

For every chat returned:

1. Match it to a CRM lead by **`external_id`** (primary), falling back to **`phone`** if no `external_id` match exists.
2. Compare `chat.status_changed_at` with the lead's stored **`last_sync_at`**.
   - If `status_changed_at > last_sync_at` → **apply the update** and set `last_sync_at = status_changed_at`.
   - Otherwise → **skip** (already current; makes reruns idempotent).
3. If no lead matches, **create** a new lead from the payload.

After the whole run succeeds, the CRM advances its watermark to the run start time.

---

## 7. Real‑time Sold webhook (Sophia pushes to CRM)

The instant an agent sets a chat's label to **Sold**, Sophia immediately calls:

### Endpoint (CRM builds)

```http
POST https://ghaithtravel.pythonanywhere.com/api/whatsapp/sync/sold/
X-Webhook-Secret: <CRM_WEBHOOK_SECRET>
Content-Type: application/json
```

### Request body

Same chat object as §6, with `status` fixed to `sold`:

```json
{
  "external_id": "wa_84f2c9e1",
  "name": "Sara Haddad",
  "phone": "+96170123456",
  "department": "turkey",
  "status": "sold",
  "status_changed_at": "2026-07-31T21:40:00+03:00",
  "destination": "Antalya",
  "chat_summary": "Confirmed 7-night package, 2 adults, travelling 12 Aug.",
  "assigned_agent": null
}
```

**Financials are not required.** Sales complete pricing/invoicing inside the CRM. The webhook only flips the lead to **Sold**; the CRM records the sale timestamp from `status_changed_at`.

### CRM behaviour
- Match/create the lead exactly as in §6 (by `external_id`, then `phone`).
- Mark it Finalized + **sold**, set `last_sync_at = status_changed_at`.
- Idempotent: re‑sending the same Sold event is a no‑op.

### CRM response

```json
// 200 OK
{ "ok": true, "lead_id": 1042, "created": false }
```

### Retries
If the CRM returns a non‑2xx or times out, Sophia should **retry with exponential backoff** (e.g. after 1m, 5m, 30m, then hourly for up to 24h). Because the operation is idempotent, safe retries will not create duplicates. As a safety net, any Sold chat that never reached us is also caught by the next 07:00 batch.

---

## 8. Field mapping (Sophia → CRM)

| Sophia field | CRM field | Required | Notes |
|--------------|-----------|----------|-------|
| `external_id` | `external_id` | Yes | Stable, unique per chat. Primary match key. |
| `name` | `name` | Yes (on create) | |
| `phone` | `phone` | Yes (on create) | E.164 recommended, e.g. `+96170123456`. Fallback match key. |
| `department` | department | Yes (on create) | Must be an `id` from §5. |
| `status` | status/stage | Yes | One of §2 values. |
| `status_changed_at` | drives sync | Yes | ISO 8601 with offset. |
| `destination` | `destination` | No | Free text; added to CRM catalog if new. |
| `chat_summary` | chat summary / notes | No | Latest AI/agent summary. |
| `assigned_agent` | `assigned_to` (+ department) | No | Stable Sophia agent id (same id as `GET /departments`). CRM maps it to a user; the lead's department comes from that user's profile. Otherwise CRM auto‑assigns by payload `department`. |
| `last_customer_message_at` | `last_customer_message_at` | No | ISO 8601. |
| `last_agent_action_at` | `last_agent_action_at` | No | ISO 8601. |
| `email` | `email` | No | |

**Ownership:** this integration is **one‑way** (Sophia → CRM). The CRM does not push lead status back to Sophia. On a fielded conflict, the value from Sophia's payload wins for the fields listed above.

---

## 9. Error responses (both endpoints)

```json
{ "error": "Human-readable message", "code": "ERROR_CODE", "details": {} }
```

| HTTP | Code | Meaning |
|------|------|---------|
| 401 | `UNAUTHORIZED` | Missing/invalid token or webhook secret |
| 400 | `INVALID_JSON` | Body is not valid JSON |
| 400 | `MISSING_FIELDS` | Required field missing |
| 400 | `INVALID_DEPARTMENT` | Unknown department id |
| 400 | `INVALID_STATUS` | Status outside the fixed list |
| 400 | `INVALID_DATE` | Timestamp missing offset or malformed |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method |

For the **pull** endpoints Sophia builds, please mirror the same shape so our client can log failures uniformly.

---

## 10. What each side builds

**Sophia builds**
- `GET /api/crm/departments/` (§5)
- `GET /api/crm/chats/?status_changed_since=…&page=…` (§6), with pagination and `status_changed_at` on every chat.
- Outbound **Sold webhook** POST to the CRM (§7), with retry/backoff.
- Issue a bearer token to the CRM; accept a webhook secret from the CRM.

**CRM builds**
- Scheduled 07:00 Asia/Beirut job that pulls departments then changed chats, applies the §6 decision logic, and advances the watermark.
- `POST /api/whatsapp/sync/sold/` webhook receiver (§7), idempotent.
- Storage for `last_sync_at` per lead and the global pull watermark.

---

## 11. Out of scope

- Creating CRM orders, invoices, clients, payments, or supplier data.
- Two‑way messaging (agents stay in the WhatsApp app / Sophia dashboard).
- Pushing CRM status changes back to Sophia.

---

## 12. Open items to confirm with Sophia

1. Sophia base URL and the bearer token issuance process.
2. Confirm the department `id`s above match what your dashboard already uses (same list on both sides).
3. ~~Confirmation that agent assignment stays with the CRM~~ — **Confirmed:** `assigned_agent` is the stable agent id returned by `GET /departments` and never changes; the CRM maps it to a user and derives the department from that user (see §5).
4. Webhook retry/backoff policy and how long they persist unacknowledged Sold events.
5. Expected daily volume (to size pagination and the batch window).
