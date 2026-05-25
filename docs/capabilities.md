# Authoring a capability

A **capability** is the unit of pluggable functionality in Atlas. The Content Creation department wires five (`script_versioning`, `asset_review_with_timecodes`, `location_scouting`, `participant_roster`, `event_scheduling`). The Marketing department wires one (`participant_roster` in lead mode). Adding a new capability — a Dutch calling bot, an outbound email sequencer, a hello_world — is a backend dir + a frontend dir + two registry entries. No core code changes.

This guide is the contract.

## Directory contract

### Backend

```
app/capabilities/<key>/
├── __init__.py
├── README.md          ← what this capability does, scope, integration notes
├── router.py          ← FastAPI router(s); always required
├── models.py          ← optional — capability-specific SQLAlchemy models
└── service.py         ← optional — domain logic (no FastAPI imports)
```

If the capability has its own tables, the SQLAlchemy modules go in `models.py` here, and `alembic/env.py` gets one line importing them so autogenerate picks them up.

### Frontend

```
frontend/src/features/capabilities/<key>/
├── api.ts                      ← apiFetchAuthed wrappers; no raw fetch()
├── types.ts                    ← TS mirror of the backend's Pydantic DTOs
├── components/
│   └── ProjectTab.tsx          ← the tab component declared in the registry
├── hooks/                      ← optional
└── index.ts                    ← optional re-export bundle
```

The component imported by `features/capabilities/registry.ts` is conventionally `<Key>Tab` (e.g. `ScriptTab`, `EditsTab`), but the registry entry's `ProjectTab` field is just a `ComponentType<any>` — whatever you point it at, that's the project-detail tab.

## Registry entry shapes

### Backend (`app/capabilities/registry.py`)

```python
"hello_world": Capability(
    key="hello_world",
    name="Hello World",
    routers=(hello_world_module.router,),
    permission_actions=("hello_world.greet",),
    event_keys=("hello_world.greeted",),
)
```

`Capability` is the dataclass in `app/capabilities/registry.py`. Required fields: `key`, `name`, `routers`. Optional: `permission_actions` (tuple of action keys this capability declares), `event_keys` (tuple of notification event keys), `default_role_permissions` (dict of `{role_key: [action_key, ...]}` seeded into templates that include the capability).

### Frontend (`frontend/src/features/capabilities/registry.ts`)

```typescript
hello_world: {
  key: "hello_world",
  tabLabelKey: "tab_hello",
  name: "Hello",
  ProjectTab: HelloWorldTab,
},
```

`tabLabelKey` resolves under `project_detail.*` in `frontend/messages/{nl,en}.json`. The `name` field is the English fallback if the i18n key is missing — a department whose template ships a `terminology` override for `tabLabelKey` shadows both.

## Convention namespaces

| Surface | Pattern | Example |
|---|---|---|
| Route prefix | `/projects/{project_id}/<resource>` or top-level `/<resource>` | `/projects/{project_id}/scripts/versions` |
| Permission action key | `<capability_key>.<verb>` | `script_versioning.lock` |
| Notification event key | `<capability_key>.<event>` | `cut_uploaded` (legacy from Phase 3 — newer capabilities should namespace) |
| Stage-move action | `stage.move:<from>-><to>` | `stage.move:idea->script_drafting` (owned by the stage machinery, not capabilities) |
| Frontend i18n | `capabilities.<key>.*` | `capabilities.hello_world.greeting` |
| GCS object key | `business/{business_id}/<capability>/<resource>/<file>` | `business/abc/edits/cut_v3.mp4` |

## Template defaults

When a capability ships in a `default_capabilities` list inside a template (`app/seeds/templates/<template>.py`), the template can also carry:

* `default_role_permissions` — array of `{role_key, action_key, allowed}` triples. Capabilities should document which action keys they declare in their `README.md` so template authors know what to grant.
* `default_capability_configs` — JSONB object keyed by capability key. Phase C added this for `participant_roster` (cast vs lead mode). Reading it from the frontend goes through `project.department.capability_configs.<key>`.
* `default_terminology` — `{noun_key: {locale: label}}` overrides. Used to render "+ New lead" instead of "+ New project" in Marketing, etc. The `useTerminology` hook does the lookup.

## Permissions runtime

`permission_service` is the single source of truth for "can this user do X." Capabilities don't roll their own checks. The two predicates capabilities call:

```python
await permission_service.can_user_perform_action(
    session,
    user=user,
    department_id=project.department_id,
    action_key="hello_world.greet",
    request=request,
)
```

Returns True if the user's `department_membership` carries a role whose `department_role_permissions` row matches `action_key` with `allowed=true`. CEO super-admins short-circuit. The map is cached per-request at `request.state.permission_cache`.

```python
await permission_service.can_user_access_project(
    session,
    user=user,
    project=project,
    level="view",  # or "edit" / "manage"
    request=request,
)
```

Wraps the membership check with project-owner short-circuits.

Frontend equivalent — wired the same way:

```typescript
const allowed = useCanIDo(departmentId, "hello_world.greet");
```

## Worked example: `hello_world`

A 30-minute capability that adds a "Hello, {{owner}}!" tab to projects when the department enables it.

### 1. Backend skeleton

```python
# app/capabilities/hello_world/__init__.py
"""hello_world — sample capability documented in docs/capabilities.md."""
```

```python
# app/capabilities/hello_world/router.py
"""GET /projects/{project_id}/hello — returns a greeting for the project owner."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth.capability_guard import require_capability
from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    require_project_access,
)
from app.models.project import ProjectModel
from app.services import permission_service

router = APIRouter(
    prefix="/projects/{project_id}/hello",
    tags=["hello_world"],
    dependencies=[Depends(require_capability("hello_world"))],
)


@router.get("", summary="Greeting for the project owner")
async def get_hello(
    project: Annotated[
        ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))
    ],
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> dict[str, str | bool]:
    allowed = await permission_service.can_user_perform_action(
        session,
        user=user,
        department_id=project.department_id,
        action_key="hello_world.greet",
        request=request,
    )
    return {
        "message": f"Hello, {project.owner.name}!",
        "can_greet": allowed,
    }
```

```python
# app/capabilities/registry.py — add to REGISTRY
from app.capabilities.hello_world import router as hello_world_module

# inside REGISTRY:
"hello_world": Capability(
    key="hello_world",
    name="Hello World",
    routers=(hello_world_module.router,),
    permission_actions=("hello_world.greet",),
    event_keys=(),
),
```

`require_capability("hello_world")` 404s if the project's department doesn't list `hello_world` in its `capabilities` JSONB array. No other code changes — `app/main.py` already iterates the registry and mounts every router on startup.

### 2. Frontend skeleton

```typescript
// frontend/src/features/capabilities/hello_world/api.ts
import { apiFetchAuthed } from "@/lib/api-client";

export function fetchHello(projectId: string): Promise<{ message: string; can_greet: boolean }> {
  return apiFetchAuthed(`/projects/${projectId}/hello`);
}
```

```tsx
// frontend/src/features/capabilities/hello_world/components/HelloTab.tsx
"use client";

import { useEffect, useState } from "react";

import type { Project } from "@/features/projects/types";

import { fetchHello } from "../api";

export function HelloTab({ project }: { project: Project }) {
  const [data, setData] = useState<{ message: string; can_greet: boolean } | null>(null);
  useEffect(() => {
    fetchHello(project.id).then(setData);
  }, [project.id]);
  return <p>{data?.message ?? "Loading…"}</p>;
}
```

```typescript
// frontend/src/features/capabilities/registry.ts — add an entry
import { HelloTab } from "@/features/capabilities/hello_world/components/HelloTab";

// inside CAPABILITY_REGISTRY:
hello_world: {
  key: "hello_world",
  tabLabelKey: "tab_hello",
  name: "Hello",
  ProjectTab: HelloTab,
},
```

### 3. i18n

```json
// frontend/messages/en.json
"project_detail": {
  ...
  "tab_hello": "Hello"
}
```

```json
// frontend/messages/nl.json
"project_detail": {
  ...
  "tab_hello": "Hallo"
}
```

### 4. Enable it on a department

```sql
UPDATE departments
   SET capabilities = capabilities || '["hello_world"]'::jsonb
 WHERE slug = 'content-creation';
```

Or via the existing department editor UI — paste the capability key into the comma-separated list and Save.

### 5. See it land

`make dev` + `make dev-web`, reload `localhost:3001/projects/<id>`. The "Hello" tab renders. Disable the capability via the same UI and the tab disappears.

That's the contract. The five existing capabilities in `app/capabilities/` are real-world examples of each piece; read `participant_roster/` first because it's the simplest, then `script_versioning/` for the full surface (versions, comments, locking, Google Doc import).

## Migrations for capability-owned tables

If your capability adds new tables (e.g. `outbound_calls`, `lead_intakes`):

1. Create the SQLAlchemy model under `app/capabilities/<key>/models.py`.
2. Add `from app.capabilities.<key> import models as _<key>_models  # noqa: F401` to `alembic/env.py` so autogenerate sees the metadata.
3. Run `make db-migration MSG="add <key> tables"` and review.
4. Add the shared `tenant_isolation` RLS policy to any business-scoped table — mirror the pattern in `alembic/versions/20260525_e8f3c1a2b9d4_phasea_multi_business_scaffolding.py`. Every business-scoped row carries a denormalised `business_id` so the policy filter stays cheap.

## Notification events

`push_service.notify_user` accepts `(event_key, department_id)`. To wire a new event:

1. Add the key to your capability's `event_keys` tuple in the registry.
2. Seed a row into `department_event_definitions` either via migration (for system templates) or via the admin UI.
3. Call `await notify_user(..., event_key="your.event", department_id=...)` from your service code at the moment of the event.

User preferences live in `user_notification_pref_events`. The fail-open default ships unknown events to every user; per-event opt-out is per-(user, department) via the Settings page.

## Capability lifecycle

* **Stub**: directory exists with a `README.md` describing planned scope. Not in the registry. See `app/capabilities/lead_inbox/`, `outbound_caller/`, `outbound_email_sequence/` for the convention.
* **Active**: registered in `app/capabilities/registry.py` + `frontend/src/features/capabilities/registry.ts`, with at least one default template referencing it.
* **Deprecated**: removed from new templates' `default_capabilities`, but still in the registry. Existing departments that enabled it keep working until they remove it themselves.
* **Removed**: registry entry deleted, code deleted, migration drops any owned tables. See Phase D's sweep of legacy `app/routes/{scripts,…}.py` for the pattern.

## What NOT to do

* Don't import from `app.routes.*` — those modules existed pre-Phase-D and are gone now. All HTTP surface lives under `app/capabilities/<key>/router.py` (capability routes) or `app/routes/` (cross-cutting: auth, health, projects).
* Don't roll your own permission check. Always go through `permission_service`.
* Don't bypass `apiFetchAuthed` on the frontend. `scripts/check-no-raw-fetch.sh` enforces this and runs on every `make lint`.
* Don't read directly from `app/models/enums.py::Role` for role gating. `Role.CEO` stays as the global super-admin bit; everything else is per-department in `department_role_permissions`.
* Don't hardcode stage keys. Templates own them; per-department renames are supported. Compare via `project.stage.key` against a key declared by the capability's template, and gracefully no-op if the department doesn't model that key.
