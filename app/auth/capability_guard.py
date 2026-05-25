"""Capability guard — returns 404 if the targeted department doesn't have
the capability enabled.

Use as a FastAPI dependency on every route inside a capability:

    require_script_versioning = require_capability("script_versioning")

    @router.post("/projects/{project_id}/scripts/...", dependencies=[Depends(require_script_versioning)])
    async def post_version(...): ...

The dependency reads `project.department.capabilities` (JSONB array) and
rejects with a 404 if the key isn't present. 404 (rather than 403) is
deliberate: from the caller's perspective the URL doesn't exist when the
capability isn't enabled.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import HTTPException, Path, status
from sqlalchemy import select

from app.auth.dependencies import SessionDep
from app.models.department import DepartmentModel
from app.models.project import ProjectModel


def require_capability(
    capability_key: str,
) -> Callable[..., Awaitable[None]]:
    """Build a dependency that 404s if the project's department doesn't have
    `capability_key` enabled.

    Routes inside a capability take a `project_id` path parameter, so the
    dependency walks `project_id -> project.department_id -> capabilities`.
    """

    async def _dep(
        session: SessionDep,
        project_id: Annotated[uuid.UUID, Path()],
    ) -> None:
        project = await session.get(ProjectModel, project_id)
        if project is None or project.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        result = await session.execute(
            select(DepartmentModel.capabilities).where(
                DepartmentModel.id == project.department_id
            )
        )
        caps = result.scalar_one_or_none() or []
        if capability_key not in caps:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Capability '{capability_key}' not enabled for this department",
            )

    return _dep


__all__ = ["require_capability"]
