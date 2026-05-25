# lead_inbox capability — design sketch

**Status:** stub. Not wired into `app/capabilities/registry.py`. Phase D claimed the directory + locked conventions; the actual implementation is a follow-up project.

## Scope

A first-class "inbound lead" pipeline that layers on top of the Phase B/C `participant_roster` primitives.

The Marketing template already uses `participant_roster` in `kind="lead"` mode for a manually-curated lead list. `lead_inbox` is the *automated* variant — intake forms, deduplication, assignment, status board — for businesses with high lead volume that can't be hand-managed.

## Capability registry entry (planned)

```python
"lead_inbox": Capability(
    key="lead_inbox",
    name="Lead Inbox",
    routers=(...),
    permission_actions=(
        "lead_inbox.assign",
        "lead_inbox.merge",
        "lead_inbox.dismiss",
        "lead_inbox.bulk_action",
    ),
    event_keys=(
        "lead_received",
        "lead_assigned",
        "lead_stale",
    ),
)
```

## Data model

Piggybacks on the `participants` table (renamed from `cast_members` in Phase C). The lead-mode rows already exist there with `kind="lead"`, `source`, `notes`. `lead_inbox` extends that:

- `lead_intakes` — one row per incoming form submission / API call. Columns: `id`, `business_id`, `department_id`, `raw_payload jsonb`, `source` (webhook / api / csv / email_parser), `received_at`, `processed_participant_id` (FK to participants when promoted to a tracked lead, nullable while still in inbox).
- `lead_dedupe_keys` — derived index columns (`normalized_email`, `normalized_phone`, `name_soundex`) for fast lookup during intake.

## Routes (planned)

```
POST   /lead-inbox/webhook            — anonymous intake (signed by HMAC)
GET    /departments/{id}/lead-inbox   — list intakes pending review
POST   /lead-inbox/{intake_id}/promote — convert intake → participant
POST   /lead-inbox/{intake_id}/dismiss — mark intake as junk
POST   /lead-inbox/bulk/assign        — assign N intakes to a user
```

## Notification event keys

- `lead_received` — every new intake fires a push to anyone with `lead_inbox` membership.
- `lead_assigned` — when an intake is assigned to a user.
- `lead_stale` — an intake unattended for >N hours.

## Out of scope (for the first implementation)

- Lead scoring / enrichment (Clearbit-style). Add later via a separate `lead_enrichment` capability.
- Automated email follow-ups — that's `outbound_email_sequence` (separate slot).
