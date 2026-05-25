# outbound_caller capability — design sketch

**Status:** stub. The Dutch AI calling bot is explicitly out of scope for Phases A-D per `project_spec.md` — this directory claims the slot for the future multi-week project.

## Scope

A capability that lets a Marketing / Sales / Lead-gen department place automated outbound calls to leads, conduct a short qualification conversation in Dutch, and write the outcome back to the `participants` row.

## Stack (provider candidates)

| Layer | Candidates |
|---|---|
| Telephony | **Twilio Programmable Voice** (mature, EU presence) or **Vonage** (incl. Dutch DID provisioning) |
| Speech-to-text (nl-NL) | **Microsoft Azure Speech** (best Dutch accuracy of the big three), **Google Cloud STT**, **Deepgram Nova** |
| LLM dialog | **Claude Sonnet** (current generation) via the existing Anthropic SDK; fall back to GPT-4o if rate limits hit |
| Text-to-speech (nl-NL) | **ElevenLabs** (most natural Dutch voices), **Azure Speech TTS** (cheapest), **Google Cloud TTS** |
| Recording storage | Existing GCS `gcs_bucket_assets` bucket under `business/{business_id}/calls/{call_id}.opus` |

The actual selection should be benchmarked against ~20 Dutch test conversations before committing — accent handling on regional Dutch (Limburgs, West-Vlaams) varies significantly between vendors.

## Capability registry entry (planned)

```python
"outbound_caller": Capability(
    key="outbound_caller",
    name="Outbound Caller",
    routers=(...),
    permission_actions=(
        "outbound_caller.initiate",
        "outbound_caller.cancel",
        "outbound_caller.review_recording",
    ),
    event_keys=(
        "call_initiated",
        "call_completed",
        "call_failed",
        "call_recording_ready",
    ),
)
```

## Data model

- `outbound_calls` — one row per attempted call. Columns: `id`, `business_id`, `department_id`, `participant_id`, `initiated_by_user_id`, `phone_number`, `status` (queued / in_progress / completed / no_answer / failed), `recording_gcs_object`, `transcript`, `llm_summary`, `outcome` (qualified / not_interested / callback_requested / etc.), `started_at`, `ended_at`.
- `outbound_call_events` — append-only event log per call (`dtmf_received`, `silence_detected`, `barge_in`, `human_takeover_requested`).

## Routes (planned)

```
POST   /outbound-calls                    — initiate a call (body: participant_id, script_id)
POST   /outbound-calls/{id}/cancel        — hang up an in-progress call
GET    /outbound-calls/{id}               — fetch metadata + recording URL
GET    /outbound-calls/{id}/recording-url — signed GCS read URL (15 min TTL)
POST   /webhooks/twilio                   — telephony provider webhook (status events)
```

## GDPR / AVG compliance (spec §10)

Phase 5 deployment notes already provision a 30-day retention default. `outbound_calls` must additionally:

- Require explicit **consent confirmation** from the called party in the opening dialog ("Dit gesprek wordt opgenomen voor kwaliteitscontrole — gaat u akkoord?"). The LLM must hang up if the response is `nee` / negative.
- Tag every recording with a `consent_recorded_at` timestamp; recordings without consent are deleted within 24 h.
- Surface a "delete my data" entrypoint in the participant detail page that nukes both the `participants` row and every linked `outbound_calls` recording + transcript.

## Per-business phone number provisioning

Twilio supports buying DIDs programmatically. Each business that enables `outbound_caller` gets exactly one Dutch number provisioned at capability-enable time. Number lives on `businesses.outbound_caller_phone_number` (a new column added by the capability's migration). Inbound calls to that number ring through to a fallback voicemail (or, later, route to whatever in-app inbox we build).

## Out of scope (initial release)

- Multi-language support — Dutch only at launch.
- A/B-testing dialog scripts — needs a separate scripts library + experiment tracking.
- Real-time human takeover — start with "call gets transferred to a human inbox on failure" only.
