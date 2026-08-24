# Reply to the Sophia team — Ghaith CRM go-live

Sophia already sent the Integration Guide (v1.1) and the credentials doc. This is
the reply to send back, answering their open items (credentials §5 / guide §11).

---

Hi team,

Thanks — we received the Integration Guide and the credentials. We've configured
our side with the base URL, bearer token, and webhook secret you provided.

## Our Sold-receiver URL (credentials §3)

```
POST https://ghaithtravel.pythonanywhere.com/api/whatsapp/sync/sold/
```

- We verify your `X-Webhook-Secret` header (`whsec_…`) with a constant-time compare.
- Body: the chat object with `status` fixed to `sold`, exactly as in guide §7.
- Success response: `{ "ok": true, "lead_id": <id>, "created": true|false }`.
- The receiver is idempotent — re-sending the same Sold event is a no-op.

## Answers to your open items

- **Agents / departments (credentials §5).** Please confirm each of our agents is
  set up on your side so they appear in `GET /departments`. We map each returned
  agent `id` to a CRM user and take the department from that user. Please send us
  the current agent list (`id` + name) so we can finish that mapping before go-live.
- **Retry window (§5).** Your 24h retry/backoff is fine. We also run the 07:00
  Asia/Beirut batch as a safety net, so any Sold that misses the webhook is picked
  up the next morning.
- **Status map (guide §11.1).** The six status values are wired on our side
  (new → On Hold, progress → Processing, offer_sent → Negotiation, sold →
  Finalized/sold, lost → Finalized/lost, unqualified → Unqualified).
- **Departments (guide §11.2).** Please share the final department/agent `id`s so
  we confirm they line up with our records.
- **Volume (guide §11.6).** No constraints on our side; our pull is paginated and
  follows `next_page`.

Ready to test whenever the account is live.

Thanks!

---

## Internal notes (do NOT send to Sophia)

Configure these on production (`ghaithleads/settings.py` or environment). Copy the
real token/secret from the `GHAITH-LEADSYNC-CREDENTIALS` PDF — do not commit them.

```
SOPHIA_BASE_URL=https://sofiiaai-prospect.ucheed.dev/json-api/prospect-crm/v1/consumer
SOPHIA_API_TOKEN=<pull API key from the credentials PDF, starts with psk_live_>
SOPHIA_WEBHOOK_SECRET=<webhook secret from the credentials PDF, starts with whsec_>
```

- `/departments` returns **agents** (`id`, `full_name`, `email`, `phone_number`).
  For each agent, open the matching CRM user in Django admin and set their
  **Sophia agent id** = that `id`. Without this, a new Sold lead can't resolve a
  department (chats send `department: null` today) and will be rejected.
- Endpoints are relative to the base above: `GET /departments`,
  `GET /chats?status_changed_since=<ISO+offset>&page=N`.
