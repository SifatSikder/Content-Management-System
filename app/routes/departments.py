"""Department CRUD endpoints.

List + read require plain business membership. Create / rename / archive
require business admin (CEO or business owner).
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth.dependencies import (
    CurrentUser,
    SessionDep,
    require_business_admin,
    require_business_member,
)
from app.models.business import BusinessModel
from app.models.department import DepartmentModel
from app.schemas.department import (
    CreateDepartmentBody,
    DepartmentListResponse,
    DepartmentPublic,
    UpdateDepartmentBody,
)
from app.services import department_service

business_router = APIRouter(prefix="/businesses", tags=["departments"])
department_router = APIRouter(prefix="/departments", tags=["departments"])
log = structlog.get_logger(__name__)


async def _require_department_admin(
    session: SessionDep, user: CurrentUser, department: DepartmentModel
) -> None:
    """403 unless `user` is the CEO or the owner of the department's business.

    `require_business_admin()` works for `/businesses/{business_id}/...`
    routes, but `/departments/{department_id}/...` doesn't carry the
    business_id in the path. This helper does the same check after the
    department row is loaded.
    """
    if user.is_super_admin:
        return
    result = await session.execute(
        select(BusinessModel.owner_user_id).where(
            BusinessModel.id == department.business_id
        )
    )
    if result.scalar_one_or_none() != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Business admin only")


@business_router.get(
    "/{business_id}/departments",
    response_model=DepartmentListResponse,
    summary="List departments inside a business",
)
async def get_departments(
    business_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    _: Annotated[object, Depends(require_business_member)],
) -> DepartmentListResponse:
    rows = await department_service.list_departments(
        session, business_id=business_id
    )
    return DepartmentListResponse(
        items=[DepartmentPublic.model_validate(r) for r in rows]
    )


@business_router.post(
    "/{business_id}/departments",
    response_model=DepartmentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a department in a business (admin only)",
)
async def post_department(
    business_id: uuid.UUID,
    body: CreateDepartmentBody,
    user: CurrentUser,
    session: SessionDep,
    _: Annotated[BusinessModel, Depends(require_business_admin)],
) -> DepartmentPublic:
    try:
        department = await department_service.create_department(
            session,
            business_id=business_id,
            name=body.name,
            slug=body.slug,
            template_key=body.template_key,
        )
    except department_service.TemplateNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Unknown department template"
        ) from exc
    except department_service.SlugTakenError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Slug already taken in this business"
        ) from exc
    await session.commit()
    await session.refresh(department)
    return DepartmentPublic.model_validate(department)


@department_router.get(
    "/{department_id}",
    response_model=DepartmentPublic,
    summary="Get one department",
)
async def get_department(
    department_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> DepartmentPublic:
    try:
        department = await department_service.get_department(
            session, department_id=department_id
        )
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc
    return DepartmentPublic.model_validate(department)


@department_router.patch(
    "/{department_id}",
    response_model=DepartmentPublic,
    summary="Rename or edit the capabilities array",
)
async def patch_department(
    department_id: uuid.UUID,
    body: UpdateDepartmentBody,
    user: CurrentUser,
    session: SessionDep,
) -> DepartmentPublic:
    try:
        department = await department_service.get_department(
            session, department_id=department_id
        )
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc
    await _require_department_admin(session, user, department)
    await department_service.update_department(
        session,
        department=department,
        name=body.name,
        capabilities=body.capabilities,
    )
    await session.commit()
    await session.refresh(department)
    return DepartmentPublic.model_validate(department)


@department_router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a department",
)
async def delete_department(
    department_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> None:
    try:
        department = await department_service.get_department(
            session, department_id=department_id
        )
    except department_service.DepartmentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Department not found"
        ) from exc
    await _require_department_admin(session, user, department)
    await department_service.archive_department(session, department=department)
    await session.commit()
