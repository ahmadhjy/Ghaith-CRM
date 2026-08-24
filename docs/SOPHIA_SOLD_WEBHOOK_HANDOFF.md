# Reply to the Sophia team — Ghaith CRM go-live

Sophia already sent the Integration Guide (v1.1) and the credentials doc. This is
the reply to send back, answering their open items (credentials §5 / guide §11).

---

Hi team,

Thanks for the credentials — we've configured our side.

**Sold-receiver URL**

```
POST https://ghaithtravel.pythonanywhere.com/api/whatsapp/sync/sold/
```

We verify the `X-Webhook-Secret` you provided, and the receiver is idempotent
(re-sends are safe no-ops).

**Retry window**

Your 24h backoff is fine. We also run the 07:00 Asia/Beirut batch as a safety net,
so any Sold that misses the webhook is reconciled the next morning — no separate
persistence window is needed on our side.

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
