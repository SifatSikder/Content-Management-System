# Sons Real Estate — Content Production CRM
## Project Specification (Functional)

**Version**: 0.3
**Owner**: Solo developer
**Target users**: Sons Real Estate internal content team (3–6 people)
**Languages**: Dutch (default) + English
**Platform**: Mobile-first PWA (Progressive Web App)
**Stack**: Next.js 15 (React 19, TS, Tailwind v4) + FastAPI (Python 3.12, async SQLAlchemy) + PostgreSQL 16 + Redis 7, all deployed on a single **Hostinger VPS** (Ubuntu 24.04 LTS, EU region) behind **Caddy 2**. Video assets on **Google Cloud Storage** (`europe-west4`, NL) with V4 signed URLs + resumable uploads. Repo follows the user's project blueprint (uv, feature-sliced frontend, single `api-client.ts` transport).

---

## 1. Purpose

Replace the team's WhatsApp-only coordination of video productions with a single source of truth that tracks every video from idea to publication. The system must make the **editing phase** legible to the CEO: which cuts exist, what feedback is open, what's awaiting his approval.

## 2. Goals & Non-Goals

### Goals
- One place for every video project's state (no more WhatsApp scrollback)
- CEO can see, on his phone, every in-flight project and act on it
- Multi-version editing review with timestamped comments and approval
- Script revisions tracked, comparable, and lockable
- Field-friendly mobile UX for location scouting, casting, shoot day
- Dutch UI; bilingual switching

### Non-Goals (for v1)
- Customer-facing portal (interview subjects do not log in — MVP)
- In-app video editing (editors keep using Premiere/DaVinci)
- Marketing campaign analytics (this is production-side, not distribution)
- Native iOS / Android apps (PWA only)
- Payroll / invoicing / contracts (out of scope)

## 3. Personas

| Persona | Role in system | Primary screen | Devices |
|---|---|---|---|
| **CEO** | `ceo` | Dashboard + approval queue | Phone (primary), Desktop |
| **Assistant Director** | `assistant_director` | Kanban board | Desktop, Phone |
| **Junior Director** | `junior_director` | Kanban + assigned projects | Desktop, Phone |
| **Editor** | `editor` | Edit version uploads + comments resolution | Desktop |
| **Shoot crew** | `crew` | Today's shoot card | Phone |
| **Viewer** (optional) | `viewer` | Read-only kanban | Either |

> Initial role list per CEO scope. Permissions matrix in §6.

## 4. Pipeline Stages (Dutch + English)

| # | English | Dutch (working) | Auto-advance trigger |
|---|---|---|---|
| 1 | Idea / Brief | Idee / Briefing | Manual |
| 2 | Category Set | Categorie gekozen | Category selected |
| 3 | Script Drafting | Script schrijven | First script version saved |
| 4 | Script Review | Script in review | Author submits for review |
| 5 | Script Locked | Script vastgelegd | "Lock script" action by director+ |
| 6 | Location Scouting | Locatie zoeken | Location module opened |
| 7 | Casting | Casting | Location confirmed |
| 8 | Shoot Scheduled | Opname gepland | Shoot date set, cast confirmed |
| 9 | Shoot Done | Opname gedaan | "Wrap shoot" action |
| 10 | Editing | Montage | First edit version uploaded |
| 11 | Final Review | Finale review | Editor marks a cut "ready for final" |
| 12 | Approved / Published | Goedgekeurd / Gepubliceerd | CEO approves final cut |

Dutch names should be confirmed verbatim with the CEO during Phase 0 — they may use industry-specific Dutch terms.

## 5. Core User Stories

### CEO
- As CEO, I open the app on my phone and see "3 cuts await your approval" so I can act in 2 minutes between meetings.
- As CEO, I scrub a cut's timeline, leave a comment at 0:34, and tap "Request changes" — the editor is notified.
- As CEO, I see which projects are stuck (no activity > 5 days).

### Director / Assistant Director
- As director, I drag a project from "Script Locked" to "Location Scouting" and assign a scout.
- As director, I lock a script after the third revision — further edits require unlock.
- As director, I create a new project, pick category, set due date, assign owner.

### Editor
- As editor, I upload Cut V2 with a note "addressed music + pacing", check off which V1 comments I resolved.
- As editor, I see all open timestamped comments on my current cut as a checklist.

### Shoot Crew
- As crew, I open today's shoot card on my phone, see the call sheet, mark "on location", later "wrap".

### Scriptwriter (when role exists — for now, anyone with director+ role)
- As writer, I draft script V1 in markdown, save, request review. Reviewers comment inline. I revise into V2.

## 6. Role Permissions Matrix

| Action | CEO | Asst Dir | Jr Dir | Editor | Crew | Viewer |
|---|---|---|---|---|---|---|
| Create project | ✅ | ✅ | ✅ | – | – | – |
| Edit any project | ✅ | ✅ | own/assigned | own/assigned | – | – |
| Move project stage | ✅ | ✅ | own/assigned | – | – | – |
| Lock script | ✅ | ✅ | ✅ | – | – | – |
| Unlock script | ✅ | ✅ | – | – | – | – |
| Upload edit version | ✅ | ✅ | ✅ | ✅ | – | – |
| Approve cut | ✅ | ✅ | – | – | – | – |
| Mark "final approved" | ✅ | – | – | – | – | – |
| Comment on script/cut | ✅ | ✅ | ✅ | ✅ | – | – |
| View all projects | ✅ | ✅ | ✅ | ✅ | assigned only | ✅ |
| Manage users / roles | ✅ | – | – | – | – | – |

Enforced at the database level via Postgres RLS, double-checked in the app layer.

## 7. Screens (6 core + auxiliary)

### 7.1 Login
- Email magic-link (Supabase Auth). Dutch UI by default. Locale switcher.

### 7.2 Kanban Board (`/projects`)
- 12 columns matching pipeline stages.
- Cards show: title, category icon, owner avatar, due-date pill, sub-state badge (e.g., "Edit V3 · 2 open").
- Drag-drop between stages (permission-gated; some auto-advance only).
- Filter: by owner, category, "needs my attention".
- Mobile: horizontal swipe between columns; tap card to open detail.

### 7.3 Project Detail (`/projects/[id]`)
Tabs: **Brief** · **Script** · **Location** · **Casting** · **Shoot** · **Edits** · **Activity**
- Brief tab: title, category, owner, due date, description, attachments.
- Script tab: rich editor (tiptap), version list, inline comments, "Lock" button.
- Location tab: address, map, contact, scheduled date, photos, "Confirmed" toggle.
- Casting tab: list of cast members (name, role, contact, release form upload, "Confirmed" toggle).
- Shoot tab: scheduled at, call sheet upload, gear checklist, status (`scheduled`/`in progress`/`wrapped`).
- Edits tab: list of cuts (V1, V2...) — each expandable to video player with timestamped comments.
- Activity tab: chronological log of every change.

### 7.4 Edit-Version Review Player
- Custom HTML5 video player.
- Click timeline = leave timestamped comment.
- Comment list synced to player (click comment → jumps to that timestamp).
- Buttons: "Approve cut" / "Request changes".
- Side-by-side compare mode: choose any two versions, play synchronously.

### 7.5 CEO Dashboard (`/dashboard`)
- "Awaiting your approval" queue (cuts + final approvals)
- In-flight projects count by stage (mini histogram)
- "Stuck" projects (no activity > 5 days, configurable)
- Weekly throughput: # videos published this week / month
- Time-in-stage averages (powered by PostHog or computed from `activity` table)

### 7.6 Settings (`/settings`)
- Profile (name, locale)
- Notification preferences (web push on/off per event type; WhatsApp on/off)
- Admin only: user management, role assignment, WhatsApp group ID config

### Auxiliary
- 404, error states, offline indicator (PWA), install prompt banner

## 8. Notifications

### Events that trigger notifications
| Event | Recipients | Channels |
|---|---|---|
| Project created | Assigned owner | Web push |
| Script submitted for review | Director+ | Web push + WhatsApp |
| Script locked | Project owner, CEO | Web push + WhatsApp |
| New cut uploaded | Director+, CEO | Web push + WhatsApp |
| Cut comment added | Editor + cut author | Web push |
| Cut approved | Editor | Web push + WhatsApp |
| Cut changes requested | Editor | Web push + WhatsApp |
| Project published | Whole team | WhatsApp digest |
| Project stuck (>5d) | CEO + owner | Web push (daily digest) |

### WhatsApp bridge
- Outbound only (system → group). Inbound parsing is out of scope.
- Group ID configured in `/settings`.
- Each message includes a deep link back to the relevant project tab.
- Rate-limited so a busy day doesn't spam the group.

## 9. Internationalisation

- All UI strings via `next-intl`.
- Locale files: `nl.json` (default), `en.json`.
- Pipeline stage names also localised (table in §4).
- Date formats follow locale (Dutch: `dd-MM-yyyy`).

## 10. Data Retention & GDPR/AVG

- Internal team only — no customer PII in the system (interview subjects' info stored as cast contacts, with release-form file).
- All deletions soft-deleted with 30-day window, then purged.
- Activity log is append-only but redacted of PII on user deletion.
- Hosted in EU regions (Supabase EU, Vercel EU edge) for AVG compliance.

## 11. Integrations

| Integration | Purpose | Phase |
|---|---|---|
| Google Cloud Storage (`google-cloud-storage`) | Video + asset storage with V4 signed URLs + resumable uploads | Phase 1 |
| Google Maps Platform (Geocoding + Places APIs) | Location autocomplete + map preview | Phase 2 |
| Google Drive API (`google-api-python-client`) | Import footage links + Google Docs into script editor | Phase 3 |
| WhatsApp Cloud API (Meta) | Outbound notifications | Phase 3 |
| Web Push (VAPID) via `pywebpush` | In-app push notifications | Phase 2 |
| PostHog | Funnel + usage analytics | Phase 4 |
| Resend | Magic-link delivery + digest emails | Phase 1 |
| Redis 7 + `arq` (on the VPS) | Background jobs (notifications, future transcoding) | Phase 2 |
| Caddy 2 + Let's Encrypt | TLS termination + automatic SSL renewal | Phase 0 |

## 12. Acceptance Criteria (per phase)

### Phase 1 — MVP
- A new user receives magic-link, logs in, sees Dutch UI.
- CEO creates a project, sets category, drags through stages.
- Director writes script V1, locks at V3.
- Editor uploads cut V1 (MP4 up to 2 GB), leaves a timestamped comment, marks "request changes".
- CEO approves a cut from his phone.
- RLS verified: a `crew` user can only see assigned projects.

### Phase 2 — Field features
- Crew member opens today's shoot card on phone offline (cached), marks status.
- Location can be created with photo upload from phone camera.
- PWA install banner appears on iOS Safari and Android Chrome.
- Web push notification arrives within 30 seconds of a triggering event.

### Phase 3 — WhatsApp + dashboards
- "New cut uploaded" message arrives in the configured WhatsApp group with a deep link that opens the cut.
- CEO dashboard shows accurate counts, identifies a stuck project after 5 idle days.
- Google Doc can be imported into a script as V1.

### Phase 4 — Polish
- Global search finds a project by title, a cast member by name, or a script keyword.
- PDF export of a project's history is generated in <10 seconds.
- PostHog funnel shows time-in-stage for each pipeline column.

## 13. Open Items (resolve in Phase 0)

- Exact Dutch pipeline-stage names (verify with CEO).
- Whether "Junior Director" can approve cuts (current matrix says no — confirm).
- Whether the team wants release-form e-signature (probably out of scope; just file upload).
- WhatsApp group: dedicated production group, or existing main group?
- Where domain will be hosted (subdomain of sonsrealestate.nl preferred).
