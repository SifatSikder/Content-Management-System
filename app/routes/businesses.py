"""Business CRUD endpoints — CEO only.

Business creation, rename, list, and soft-delete. Membership management
lives in `business_memberships.py`; department CRUD lives in
`departments.py`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import (
    CurrentUser,
    SessionDep,
    require_role,
)
from app.models.enums import Role
from app.schemas.business import (
    BusinessListResponse,
    BusinessPublic,
    CreateBusinessBody,
    UpdateBusinessBody,
)
from app.services import business_service

router = APIRouter(prefix="/businesses", tags=["businesses"])
log = structlog.get_logger(__name__)

CeoOnly = require_role(Role.CEO)


@router.post(
    "",
    response_model=BusinessPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a business (CEO only)",
)
async def post_business(
    body: CreateBusinessBody,
    user: Annotated[CurrentUser, Depends(CeoOnly)],
    session: SessionDep,
) -> BusinessPublic:
    business = await business_service.create_business(
        session, actor=user, name=body.name, slug=body.slug
    )
    await session.commit()
    await session.refresh(business)
    return BusinessPublic.model_validate(business)


@router.get("", response_model=BusinessListResponse, summary="List businesses")
async def get_businesses(
    user: CurrentUser,
    session: SessionDep,
) -> BusinessListResponse:
    businesses = await business_service.list_businesses(session)
    return BusinessListResponse(
        items=[BusinessPublic.model_validate(b) for b in businesses]
    )


@router.get(
    "/{business_id}",
    response_model=BusinessPublic,
    summary="Get one business",
)
async def get_business(
    business_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> BusinessPublic:
    try:
        business = await business_service.get_business(session, business_id=business_id)
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found") from exc
    return BusinessPublic.model_validate(business)


@router.patch(
    "/{business_id}",
    response_model=BusinessPublic,
    summary="Rename / update a business (CEO only)",
)
async def patch_business(
    business_id: uuid.UUID,
    body: UpdateBusinessBody,
    user: Annotated[CurrentUser, Depends(CeoOnly)],
    session: SessionDep,
) -> BusinessPublic:
    try:
        business = await business_service.get_business(session, business_id=business_id)
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found") from exc
    try:
        await business_service.update_business(
            session, business=business, name=body.name, slug=body.slug
        )
    except business_service.SlugTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken") from exc
    await session.commit()
    await session.refresh(business)
    return BusinessPublic.model_validate(business)


@router.delete(
    "/{business_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a business (CEO only)",
)
async def delete_business(
    business_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(CeoOnly)],
    session: SessionDep,
) -> None:
    try:
        business = await business_service.get_business(session, business_id=business_id)
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found") from exc
    await business_service.soft_delete_business(session, business=business)
    await session.commit()
