"""DTOs for permission lookups.

`MePermissionsResponse` is the single batched payload the frontend uses to
render kanban affordances + tab actions. Shape:

    {
      "department_id": "<uuid>",
      "is_super_admin": false,
      "allowed": { "project.create": true, "stage.move:idea->script_drafting": true, ... }
    }

CEO super-admins receive `is_super_admin = true` and an empty `allowed` map
— the frontend treats the bit as "everything allowed" without enumerating
every action.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class MePermissionsResponse(BaseModel):
    department_id: uuid.UUID
    is_super_admin: bool
    allowed: dict[str, bool]


__all__ = ["MePermissionsResponse"]
