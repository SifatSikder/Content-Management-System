"""`/me/...` lookups: businesses + departments the current user belongs to.

Both endpoints intentionally bypass RLS via `is_super_admin=true` on the
query — they're naturally scoped to `user.id`, and without the bypass a
user with multiple business memberships would only see whichever business
the middleware happened to pick from the request.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import select, text

from app.auth.dependencies import CurrentUser, SessionDep
from app.models.business import BusinessModel
from app.models.business_membership import BusinessMembershipModel
from app.models.department import DepartmentModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.enums import BusinessMembershipStatus
from app.schemas.business import MeBusinessEntry, MeBusinessesResponse
from app.schemas.department import MeDepartmentEntry, MeDepartmentsResponse
from app.schemas.permission import MePermissionsResponse
from app.services import business_service, permission_service

router = APIRouter(prefix="/me", tags=["me"])
log = structlog.get_logger(__name__)


@router.get(
    "/businesses",
    response_model=MeBusinessesResponse,
    summary="Businesses the current user belongs to (or owns)",
)
async def get_my_businesses(
    user: CurrentUser, session: SessionDep
) -> MeBusinessesResponse:
    # Self-scoped query: bypass tenant RLS for this transaction so we can
    # see every business the user has a row in, not just the one currently
    # in the request's business context.
    await session.execute(text("SET LOCAL app.is_super_admin = 'true'"))

    if user.is_super_admin:
        # CEO sees every business on the platform.
        result = await session.execute(
            select(BusinessModel)
            .where(BusinessModel.deleted_at.is_(None))
            .order_by(BusinessModel.created_at.asc())
        )
        items = [
            MeBusinessEntry(
                id=b.id,
                name=b.name,
                slug=b.slug,
                is_owner=b.owner_user_id == user.id,
                membership_status=BusinessMembershipStatus.ACTIVE,
                logo_url=await business_service.build_signed_logo_url(b),
            )
            for b in result.scalars().all()
        ]
        return MeBusinessesResponse(items=items)

    rows = await session.execute(
        select(BusinessModel, BusinessMembershipModel.status)
        .join(
            BusinessMembershipModel,
            BusinessMembershipModel.business_id == BusinessModel.id,
        )
        .where(
            BusinessMembershipModel.user_id == user.id,
            BusinessModel.deleted_at.is_(None),
        )
        .order_by(BusinessModel.created_at.asc())
    )
    items = [
        MeBusinessEntry(
            id=b.id,
            name=b.name,
            slug=b.slug,
            is_owner=b.owner_user_id == user.id,
            membership_status=status,
            logo_url=await business_service.build_signed_logo_url(b),
        )
        for b, status in rows.all()
    ]
    return MeBusinessesResponse(items=items)


@router.get(
    "/departments",
    response_model=MeDepartmentsResponse,
    summary="Departments the current user has a role in for a given business",
)
async def get_my_departments(
    user: CurrentUser,
    session: SessionDep,
    business_id: Annotated[uuid.UUID, Query(...)],
) -> MeDepartmentsResponse:
    await session.execute(text("SET LOCAL app.is_super_admin = 'true'"))

    if user.is_super_admin:
        result = await session.execute(
            select(DepartmentModel)
            .where(
                DepartmentModel.business_id == business_id,
                DepartmentModel.archived_at.is_(None),
            )
            .order_by(DepartmentModel.created_at.asc())
        )
        items = [
            MeDepartmentEntry(
                id=d.id,
                business_id=d.business_id,
                name=d.name,
                slug=d.slug,
                role_key=None,
                role_name_i18n=None,
                template_key=d.template_key,
                terminology=d.terminology or {},
            )
            for d in result.scalars().all()
        ]
        return MeDepartmentsResponse(items=items)

    rows = await session.execute(
        select(DepartmentModel, DepartmentRoleModel.key, DepartmentRoleModel.name_i18n)
        .join(
            DepartmentMembershipModel,
            DepartmentMembershipModel.department_id == DepartmentModel.id,
        )
        .join(
            DepartmentRoleModel,
            DepartmentRoleModel.id == DepartmentMembershipModel.role_id,
        )
        .where(
            DepartmentMembershipModel.user_id == user.id,
            DepartmentModel.business_id == business_id,
            DepartmentModel.archived_at.is_(None),
        )
        .order_by(DepartmentModel.created_at.asc())
    )
    items = [
        MeDepartmentEntry(
            id=d.id,
            business_id=d.business_id,
            name=d.name,
            slug=d.slug,
            role_key=role_key,
            role_name_i18n=role_name_i18n,
            template_key=d.template_key,
            terminology=d.terminology or {},
        )
        for d, role_key, role_name_i18n in rows.all()
    ]
    return MeDepartmentsResponse(items=items)


@router.get(
    "/permissions",
    response_model=MePermissionsResponse,
    summary="Resolved {action_key: allowed} map for the current user in a department",
)
async def get_my_permissions(
    user: CurrentUser,
    session: SessionDep,
    department_id: Annotated[uuid.UUID, Query(...)],
) -> MePermissionsResponse:
    """Batched permission lookup the frontend uses to render kanban
    affordances + per-tab action buttons.

    For CEO super-admins, returns `is_super_admin=True` with an empty
    `allowed` map — the frontend treats that as "every action allowed".
    """
    # The default tenant policy scopes this query by the request's business;
    # the permission service reads `department_role_permissions` which the
    # request's business context already covers. No bypass needed here.
    perms = await permission_service.permissions_for_user(
        session, user=user, department_id=department_id
    )
    payload = permission_service.serialise_action_map(perms)
    return MePermissionsResponse(
        department_id=department_id,
        is_super_admin=payload["is_super_admin"],
        allowed=payload["allowed"],
    )
