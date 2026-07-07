# WhatsApp AI Dashboard → CRM Lead Sync API

This document is for the **WhatsApp AI dashboard integration team**. It describes how to synchronize **leads only** into the Ghaith CRM.

**Scope:** Lead records only. This API does **not** create or update tasks, orders, invoices, clients, or any other CRM entities.

**Production base URL:** `https://ghaithtravel.pythonanywhere.com`

---

## Authentication

Every request must include:

```http
X-API-Key: GhaithDashboard-2026-xK9mP2vL7nQ4wR8sT
Content-Type: application/json
```

**Current shared API key:** `GhaithDashboard-2026-xK9mP2vL7nQ4wR8sT`

The CRM reads this from the `EXTERNAL_API_KEY` environment variable on the server (same default in code). Change it on PythonAnywhere when you rotate the key, then update the dashboard config. Requests without a valid key receive `401 Unauthorized`.

---

## Departments

Each lead must be routed to a **department**. The CRM auto-assigns the lead to an active sales user in that department (user with the fewest open leads), unless a more specific rule applies (see **Assignment behaviour** below).

### Honeymoon & Far East — Alaa / Fouad routing

Both agents share the same department (`honeymoon_far_east`) and may share the same WhatsApp business line. Send **`chat_label`** on create/update so the CRM assigns the correct agent:

| `chat_label` (case-insensitive) | Assigned CRM user |
|--------------------------------|-------------------|
| `Fouad` | User `fouad` (must be in Honeymoon & Far East department) |
| `Alaa`, missing, or any other value | User `alaa` (fallback) |

**Fallback:** If `chat_label` is omitted but `whatsapp_received_on` is exactly `Alaa` or `Fouad` (any case), that value is used as the label.

**Admin setup:** In Django Admin → **Users** → CRM profile, set **both** Alaa and Fouad to department **Honeymoon & Far East Department** and enable **Receives lead assignments**.

### Department codes

| Code | Department name |
|------|-----------------|
| `reservation` | Reservation Department |
| `honeymoon_far_east` | Honeymoon & Far East Department |
| `sharm` | Sharm Department |
| `civil_marriage` | Civil Marriage Department |
| `turkey` | Turkey Department |

You may send either the **code** (recommended) or the full department **name**.

### List departments and users

```http
GET /api/departments/
```

**Example response:**

```json
{
  "departments": [
    {
      "code": "turkey",
      "name": "Turkey Department",
      "users": [
        {
          "id": 12,
          "username": "rayan",
          "full_name": "Rayan",
          "receives_lead_assignments": true
        }
      ]
    }
  ],
  "status_values": [
    {"value": "done", "label": "Unqualified"},
    {"value": "finalized", "label": "Finalized"},
    {"value": "followup", "label": "Follow-Up"},
    {"value": "negotiation", "label": "Negotiation"},
    {"value": "onhold", "label": "On Hold"},
    {"value": "processing", "label": "Processing"}
  ]
}
```

**CRM admin setup (after deploy):** Departments are created automatically by the database migration — you do **not** need to create them manually. After deploying, open Django Admin → **Users** → each sales user → **CRM profile** → set **Department** and ensure **Receives lead assignments** is checked.

**Before this update:** The CRM worked without departments because agents picked leads manually. Departments are only required for **API-synced leads** (auto-assignment). Existing leads and manual CRM usage are unchanged.

---

## Lead stages (status)

| API value | CRM label | Typical meaning |
|-----------|-----------|-----------------|
| `onhold` | On Hold | New lead, not yet taken by an agent |
| `processing` | Processing | Agent is qualifying the lead |
| `negotiation` | Negotiation | Offer / pricing discussion |
| `finalized` | Finalized | Deal closed (sold or lost) |
| `followup` | Follow-Up | Scheduled follow-up |
| `done` | Unqualified | Lead closed as unqualified |

List stages:

```http
GET /api/leads/stages/
```

---

## Field mapping (dashboard → CRM)

| Dashboard field | CRM field | Notes |
|-----------------|-----------|-------|
| Name | `name` | Required on create |
| Phone number | `phone` | E.164 format recommended, e.g. `+96171234567` |
| Country code + mobile | `country_code` + `mobile_number` | Legacy format; CRM stores combined `phone` |
| WhatsApp number received on | `whatsapp_received_on` | Business line that received the message (phone number or line identifier) |
| Chat label | `chat_label` | **Honeymoon & Far East only:** `Alaa` or `Fouad` for agent routing (see above) |
| Department | `department` | Code or name; required on create |
| Destination requested | `destination` | Free text or known destination name; auto-added to CRM destination list |
| Chat summary | `chat_summary` | AI summary; kept in sync with `finalization_notes` and `reason_of_travel` |
| What happened (legacy) | `what_happened` | Alias for summary on sync; updates `chat_summary` unless closing as lost |
| Last customer message at | `last_customer_message_at` | ISO 8601 datetime of last inbound customer message |
| Last agent action at | `last_agent_action_at` | ISO 8601 datetime of last agent action in the chat |
| Current lead stage | `status` | One of the stage values above |
| Dashboard lead ID | `external_id` | **Recommended** for idempotent sync |
| Channel | `channel` | Defaults to `Whatsapp` |
| Email | `email` | Optional |

---

## Create or update a lead (primary endpoint)

```http
POST /api/leads/
```

Creates a new lead, or updates an existing one when:

- `external_id` matches an existing lead, **or**
- `phone` matches an existing lead (most recent)

### Request body

```json
{
  "external_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Sara Haddad",
  "phone": "+96170123456",
  "whatsapp_received_on": "+96171111000",
  "department": "turkey",
  "destination": "Antalya",
  "chat_summary": "Customer asked about a 7-night honeymoon package in July for 2 adults.",
  "last_customer_message_at": "2026-07-02T10:12:00+03:00",
  "last_agent_action_at": "2026-07-02T10:15:00+03:00",
  "status": "onhold",
  "channel": "Whatsapp",
  "email": "sara@example.com"
}
```

**Honeymoon & Far East example** (assign to Fouad):

```json
{
  "external_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "Nour Khalil",
  "phone": "+96170999888",
  "department": "honeymoon_far_east",
  "chat_label": "Fouad",
  "destination": "Maldives",
  "chat_summary": "Honeymoon inquiry for 2 adults in September.",
  "status": "onhold"
}
```

### Required fields (new lead)

- `name` (or `first_name` + `last_name` for legacy clients)
- `phone` (or `country_code` + `mobile_number`)
- `department`

### Response `201 Created` (new lead)

```json
{
  "id": 1042,
  "external_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Sara Haddad",
  "phone": "+96170123456",
  "country_code": "+961",
  "whatsapp_received_on": "+96171111000",
  "department": "turkey",
  "department_name": "Turkey Department",
  "destination": "Antalya",
  "chat_summary": "Customer asked about a 7-night honeymoon package in July for 2 adults.",
  "status": "onhold",
  "status_label": "On Hold",
  "channel": "Whatsapp",
  "email": "sara@example.com",
  "assigned_to": {
    "id": 12,
    "username": "rayan",
    "full_name": "Rayan"
  },
  "created_at": "2026-07-02T10:15:00+00:00",
  "last_modified": "2026-07-02T10:15:00+00:00",
  "last_customer_message_at": "2026-07-02T10:12:00+03:00",
  "last_agent_action_at": "2026-07-02T10:15:00+03:00"
}
```

Datetime fields use ISO 8601 (e.g. `2026-07-02T10:15:00+03:00` or `2026-07-02T10:15:00Z`). Omit or send `null` to leave unchanged on update.

### Response `200 OK` (updated existing lead)

Same JSON shape as above.

### Assignment behaviour

1. CRM resolves the department.
2. If department is **`honeymoon_far_east`**, CRM reads **`chat_label`** (`Alaa` / `Fouad`, case-insensitive). Missing or unknown labels assign **Alaa**. See **Honeymoon & Far East** section above.
3. Otherwise, CRM selects an **active** user in that department with **Receives lead assignments** enabled (fewest open leads wins).
4. Optional override: `"assigned_to": "username"` (must belong to the department).

On department change, the lead is reassigned using the same rules (`reassign: true` by default on `PATCH`). Send `chat_label` again when reassigning Honeymoon & Far East leads.

New API leads are created with `takeover=true` so they appear in the CRM takeover queue for the assigned agent.

### Chat summary sync

`chat_summary`, `what_happened` (on sync), and CRM **What Happened** (`finalization_notes`) are kept aligned on API updates — send the latest AI summary via `chat_summary` during the conversation. When closing as **lost**, `what_happened` / `why` still sets finalization notes only for that close action.

---

## Get a lead

```http
GET /api/leads/{id}/
```

Returns the lead JSON object (same shape as create response).

---

## Update a lead

```http
PATCH /api/leads/{id}/
```

Update stage, summary, destination, or department. Example:

```json
{
  "status": "processing",
  "chat_summary": "Customer confirmed travel dates: 10–17 August.",
  "destination": "Istanbul"
}
```

When `department` changes, the lead is reassigned to a user in the new department by default (`reassign: true`). Set `"reassign": false` to keep the current owner.

`PUT` is accepted as an alias for `PATCH`.

---

## CRM workflow (all 4 steps)

The API mirrors the CRM lead pipeline. Use the dedicated endpoints where noted, or send the same fields via `PATCH /api/leads/{id}/`.

| Step | CRM screen | API status | Endpoint |
|------|------------|------------|----------|
| 1 — New lead | On Hold / takeover | `onhold` | `POST /api/leads/` |
| 2 — Qualification | Processing | `processing` → `negotiation` or `done` | `POST /api/leads/{id}/qualify/` |
| 3 — Negotiation | Negotiation | `negotiation` | `PATCH /api/leads/{id}/` |
| 4 — Close deal | Finalized / Follow-up | `finalized` or `followup` | `POST /api/leads/{id}/close-deal/` |

### Step 2 — Qualify a lead

```http
POST /api/leads/{id}/qualify/
```

Set qualification fields and choose an action with `qualification_action`:

| Action | Result |
|--------|--------|
| `save_and_exit` | Status → `processing` (save and stay in qualification) |
| `advance_to_negotiation` | Status → `negotiation` |
| `mark_unqualified` | Status → `done` (unqualified) |

**Example — advance to negotiation:**

```json
{
  "qualification_action": "advance_to_negotiation",
  "what_happened": "Client confirmed dates and budget.",
  "destination": "Antalya",
  "pax": "2",
  "duration": "7 nights",
  "budget_range_from": 800,
  "budget_range_to": 1200,
  "follow_up_date": "2026-07-10"
}
```

Optional qualification fields: `special_request`, `assignment_notes`, `why_this_destination`, `date_notes`, `urgent`, `budget_range_from`, `budget_range_to`, `follow_up_date`.

Aliases: `advance_to_negotiation: true`, `unqualified: true`, `save_and_exit: true`.

### Step 3 — Negotiation

Update the lead while in negotiation (summary, destination, notes):

```http
PATCH /api/leads/{id}/
```

```json
{
  "status": "negotiation",
  "chat_summary": "Offer sent: $1,500 for 7 nights all-inclusive."
}
```

### Step 4 — Close deal (finalization)

```http
POST /api/leads/{id}/close-deal/
```

Send `outcome` as one of `sold`, `lost`, or `postponed`. This matches the CRM **Close Deal** screen.

#### Mark as sold

Requires `selling_price` and `net`. **Profit is calculated automatically** (`selling_price − net`).

```json
{
  "outcome": "sold",
  "selling_price": "1500",
  "net": "1200"
}
```

Response includes `"profit": "300"`, `"sold": true`, `"status": "finalized"`.

#### Mark as lost

Requires `why` (same meaning as CRM “what happened” / finalization notes). Aliases: `finalization_notes`, `what_happened`.

```json
{
  "outcome": "lost",
  "why": "Client chose another agency."
}
```

Response: `"lost": true`, `"status": "finalized"`, `"finalization_notes": "..."`.

#### Postpone (follow-up)

Requires `follow_up_date` (ISO date `YYYY-MM-DD`). Alias: `follow_up`.

```json
{
  "outcome": "postponed",
  "follow_up_date": "2026-08-15"
}
```

Response: `"status": "followup"`, `"follow_up_date": "2026-08-15"`.

You can also close a deal via `PATCH /api/leads/{id}/` with the same `outcome` and fields.

---

## Search leads

```http
GET /api/leads/search/?phone=96170123456
GET /api/leads/search/?external_id=550e8400-e29b-41d4-a716-446655440000
```

**Response:**

```json
{
  "results": [ { "...lead object..." } ]
}
```

---

## Legacy endpoints (still supported)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/contacts/` | Alias for `POST /api/leads/` |
| GET | `/api/contacts/search/?phone=` | Alias for lead search |
| GET | `/api/contacts/by-phone/?phone=` | Single lead by exact phone |
| POST | `/api/contacts/{id}/follow-up/` | Set follow-up date |
| GET | `/api/destinations/` | CRM destination catalog (merged from CRM + accounting lists) |
| POST | `/api/crm/notifications/` | Supervisor notification record |

Legacy create body used `first_name`, `last_name`, `mobile_number`, `what_happened` — still accepted.

---

## Error responses

```json
{
  "error": "Human-readable message",
  "code": "ERROR_CODE",
  "details": {}
}
```

| HTTP | Code | Meaning |
|------|------|---------|
| 401 | `INVALID_API_KEY` | Missing or wrong API key |
| 400 | `INVALID_JSON` | Body is not valid JSON |
| 400 | `MISSING_FIELDS` | Required field missing |
| 400 | `INVALID_DEPARTMENT` | Unknown department |
| 400 | `INVALID_STATUS` | Unknown status value |
| 400 | `INVALID_DATE` | Bad date format (follow-up endpoint) |
| 400 | `INVALID_AMOUNT` | Bad selling_price or net |
| 400 | `INVALID_ACTION` | Unknown qualification_action |
| 400 | `NO_USER` | No assignable user in department |
| 404 | `CONTACT_NOT_FOUND` | Lead not found by phone |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method |

---

## Recommended integration flow

1. **New WhatsApp conversation** → `POST /api/leads/` with `external_id`, contact details, department, `whatsapp_received_on`, `chat_summary`, and activity timestamps (`last_customer_message_at`, `last_agent_action_at`) when available.
2. **Honeymoon & Far East** → include `chat_label`: `Alaa` or `Fouad`.
2. **Store CRM `id`** from the response in the dashboard database.
3. **Agent qualifies** → `POST /api/leads/{id}/qualify/` with fields + `qualification_action`.
4. **During negotiation** → `PATCH /api/leads/{id}/` with updated `chat_summary` / destination.
5. **Close deal** → `POST /api/leads/{id}/close-deal/` with `outcome` and the required fields (sold: prices; lost: why; postponed: follow_up_date).
6. **Optional** → `GET /api/leads/search/?phone=` before create if `external_id` is unavailable.

---

## Production deployment checklist

1. Set environment variable on PythonAnywhere (in `deploy/pythonanywhere.env` or WSGI env):
   ```bash
   EXTERNAL_API_KEY="GhaithDashboard-2026-xK9mP2vL7nQ4wR8sT"
   ```
2. Deploy CRM code and run migrations:
   ```bash
   cd /home/ghaithtravel/ghaithleads
   export DJANGO_SETTINGS_MODULE=ghaithleads.settings
   BACKUP_MEDIA=no bash deploy/deploy.sh
   ```
   Migration `0012` automatically creates all 5 departments and a CRM profile for every existing user. Migration `0013` adds `last_customer_message_at` and `last_agent_action_at` on leads.
3. In Django Admin (one-time, after deploy):
   - Confirm departments exist under **Display → Departments** (seeded by migration).
   - For each sales user: **Users** → user → **CRM profile** → pick **Department** and check **Receives lead assignments**.
4. Test with:
   ```bash
   curl -X POST https://ghaithtravel.pythonanywhere.com/api/leads/ \
     -H "X-API-Key: GhaithDashboard-2026-xK9mP2vL7nQ4wR8sT" \
     -H "Content-Type: application/json" \
     -d '{"external_id":"test-1","name":"Test Lead","phone":"+96170000099","department":"reservation","whatsapp_received_on":"+96171111000","chat_summary":"Test sync"}'
   ```

**Why departments were not needed before:** Manual CRM assignment did not use departments. They only affect **new API leads** from the WhatsApp dashboard. Deploy first, then assign departments in Admin — the CRM keeps working during that step; API sync will return `NO_USER` for a department until at least one active user is assigned there.

---

## Out of scope

The following are **not** part of this API and must not be expected from these endpoints:

- Creating CRM orders (`LeadTask`)
- Creating accounting invoices or clients
- Syncing tasks, payments, or supplier data
- Two-way WhatsApp messaging (agents continue on WhatsApp app)

---

## Support

CRM technical contact: development team maintaining the Ghaith-CRM repository.

When reporting issues, include: request URL, `external_id`, response status, and response body (redact API key).
