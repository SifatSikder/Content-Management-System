"""Stage-handoff service.

Pure (no FastAPI). Two read paths the rest of the codebase calls:
`default_assignees_for_stage` (used by `assignment_service.seed_default`
on stage transitions) and `resolve_users_for_role` (internally expands
a role id to the set of department members holding that role).

Write paths (`upsert_handoff`) are exposed for the admin UI to call
through `app/routes/department_handoffs.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department_membership import DepartmentMembershipModel
from app.models.department_stage_handoff import DepartmentStageHandoffModel

log = structlog.get_logger(__name__)


class StageHandoffNotFoundError(Exception):
    """No handoff row for that stage in that department."""


# ---- reads ---------------------------------------------------------------


async def list_handoffs(
    session: AsyncSession, *, department_id: uuid.UUID
) -> Sequence[DepartmentStageHandoffModel]:
    result = await session.execute(
        select(DepartmentStageHandoffModel)
        .where(DepartmentStageHandoffModel.department_id == department_id)
        .order_by(DepartmentStageHandoffModel.stage_key.asc())
    )
    return list(result.scalars().all())


async def get_handoff(
    session: AsyncSession, *, department_id: uuid.UUID, stage_key: str
) -> DepartmentStageHandoffModel | None:
    result = await session.execute(
        select(DepartmentStageHandoffModel)
        .where(DepartmentStageHandoffModel.department_id == department_id)
        .where(DepartmentStageHandoffModel.stage_key == stage_key)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def resolve_users_for_role(
    session: AsyncSession, *, department_id: uuid.UUID, role_id: uuid.UUID
) -> list[uuid.UUID]:
    """All user ids in `department_id` whose membership role is `role_id`."""
    result = await session.execute(
        select(DepartmentMembershipModel.user_id)
        .where(DepartmentMembershipModel.department_id == department_id)
        .where(DepartmentMembershipModel.role_id == role_id)
    )
    return [row[0] for row in result.all()]


async def default_assignees_for_stage(
    session: AsyncSession, *, department_id: uuid.UUID, stage_key: str
) -> list[uuid.UUID]:
    """Return distinct user ids to auto-assign when a project in
    `department_id` enters `stage_key`. Empty list if no handoff or
    every role in the handoff has zero members."""
    handoff = await get_handoff(
        session, department_id=department_id, stage_key=stage_key
    )
    if handoff is None or not handoff.role_ids:
        return []
    seen: set[uuid.UUID] = set()
    ordered: list[uuid.UUID] = []
    for raw_role_id in handoff.role_ids:
        try:
            role_id = uuid.UUID(raw_role_id)
        except (TypeError, ValueError):
            continue
        for user_id in await resolve_users_for_role(
            session, department_id=department_id, role_id=role_id
        ):
            if user_id in seen:
                continue
            seen.add(user_id)
            ordered.append(user_id)
    return ordered


# ---- writes --------------------------------------------------------------


async def upsert_handoff(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    department_id: uuid.UUID,
    stage_key: str,
    role_ids: list[uuid.UUID],
) -> DepartmentStageHandoffModel:
    result = await session.execute(
        select(DepartmentStageHandoffModel)
        .where(DepartmentStageHandoffModel.department_id == department_id)
        .where(DepartmentStageHandoffModel.stage_key == stage_key)
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    serialized = [str(r) for r in role_ids]
    if existing is not None:
        existing.role_ids = serialized
        await session.flush()
        return existing
    row = DepartmentStageHandoffModel(
        business_id=business_id,
        department_id=department_id,
        stage_key=stage_key,
        role_ids=serialized,
    )
    session.add(row)
    await session.flush()
    return row


__all__ = [
    "StageHandoffNotFoundError",
    "default_assignees_for_stage",
    "get_handoff",
    "list_handoffs",
    "resolve_users_for_role",
    "upsert_handoff",
]
