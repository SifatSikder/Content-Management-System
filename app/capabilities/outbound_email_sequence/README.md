# outbound_email_sequence capability — design sketch

**Status:** stub. This is the cheapest future capability to actually build — it piggybacks on the existing Gmail send + arq worker infrastructure.

## Scope

Scheduled drip campaigns per lead — N emails over M days, with personalization tokens, per-lead state tracking, and an unsubscribe link that respects the lead's preference across all sequences.

## Why this is cheap

Everything we need already exists from Phases 0-3:

- **Gmail send** — `app/services/email_service.py` already sends real mail via the CEO's mailbox using `GMAIL_OAUTH_REFRESH_TOKEN`. Per-business Gmail OAuth tokens would be added the same way (Phase D capability migrations).
- **arq worker** — `app/jobs/` already runs an arq worker via `make dev-worker`. Adding `send_sequence_step` as a scheduled job is a 30-line addition.
- **Per-user Drive OAuth** is the template for per-user Gmail OAuth if we want personal "from" addresses.

## Capability registry entry (planned)

```python
"outbound_email_sequence": Capability(
    key="outbound_email_sequence",
    name="Outbound Email Sequence",
    routers=(...),
    permission_actions=(
        "outbound_email_sequence.create",
        "outbound_email_sequence.enroll",
        "outbound_email_sequence.unenroll",
        "outbound_email_sequence.edit_template",
    ),
    event_keys=(
        "email_sent",
        "email_replied",
        "email_bounced",
        "sequence_completed",
    ),
)
```

## Data model

- `email_sequences` — one row per defined drip. Columns: `id`, `business_id`, `department_id`, `name`, `from_address`, `from_name`.
- `email_sequence_steps` — ordered steps. Columns: `id`, `sequence_id`, `order_index`, `delay_days`, `subject_template`, `body_template_markdown`, `pause_on_reply` (bool).
- `email_sequence_enrollments` — one row per (lead, sequence) pair. Columns: `id`, `business_id`, `participant_id`, `sequence_id`, `enrolled_at`, `current_step_index`, `next_send_at`, `status` (active / paused_on_reply / completed / unenrolled).
- `email_messages` — sent-mail log. Columns: `id`, `business_id`, `enrollment_id`, `step_id`, `gmail_message_id`, `sent_at`, `replied_at`, `bounced_at`.

## Routes (planned)

```
POST   /departments/{id}/email-sequences           — create sequence
PATCH  /email-sequences/{id}                       — edit
GET    /email-sequences/{id}/steps                 — list steps
POST   /email-sequences/{id}/enroll                — enroll one or many participants
POST   /email-sequence-enrollments/{id}/unenroll   — opt out
```

## arq job

```python
# app/jobs/email_sequence.py
async def tick_email_sequences(ctx: dict) -> int:
    """Cron'd every 15 minutes. For each enrollment whose `next_send_at` is
    past, render + send the current step, advance the cursor."""
```

Add to `WorkerSettings.cron_jobs` in `app/jobs/worker.py`.

## GDPR / AVG compliance

- Every outbound email carries an unsubscribe link (signed token, no auth required to use).
- Hitting the unsubscribe link sets `email_sequence_enrollments.status = 'unenrolled'` for every active enrollment of that lead AND writes a row to a global `email_optouts` table keyed by `normalized_email_hash` so future sequences for the same address don't fire.
- `participants` with an active opt-out can't be enrolled — the enroll endpoint 409s.

## Reply detection

Poll the Gmail inbox via the existing OAuth credentials every 5 minutes. Match incoming threads to `email_messages.gmail_message_id` via `In-Reply-To` / `References` headers. On match, update `replied_at` and (if `pause_on_reply`) set `status = 'paused_on_reply'`.

## Out of scope (initial release)

- Per-recipient send-time optimization. Send at the step's configured `next_send_at` exactly.
- A/B testing subject lines. Future capability extension.
- HTML editor UX — markdown only. We render the markdown to HTML at send time using the existing `markdownify` dependency in reverse.
