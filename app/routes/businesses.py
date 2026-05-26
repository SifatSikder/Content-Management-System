"""Business CRUD endpoints — CEO only.

Business creation, rename, list, and soft-delete. Membership management
lives in `business_memberships.py`; department CRUD lives in
`departments.py`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.dependencies import (
    CurrentUser,
    SessionDep,
    require_role,
)
from app.models.business import BusinessModel
from app.models.enums import Role
from app.schemas.business import (
    BusinessListResponse,
    BusinessPublic,
    CreateBusinessBody,
    FinaliseLogoBody,
    InitLogoUploadBody,
    InitLogoUploadResponse,
    UpdateBusinessBody,
)
from app.services import business_service

router = APIRouter(prefix="/businesses", tags=["businesses"])
log = structlog.get_logger(__name__)

CeoOnly = require_role(Role.CEO)


async def _to_public(business: BusinessModel) -> BusinessPublic:
    """Serialise a business with a freshly-minted signed logo URL."""
    payload = BusinessPublic.model_validate(business)
    payload.logo_url = await business_service.build_signed_logo_url(business)
    return payload


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
    return await _to_public(business)


@router.get("", response_model=BusinessListResponse, summary="List businesses")
async def get_businesses(
    user: CurrentUser,
    session: SessionDep,
) -> BusinessListResponse:
    businesses = await business_service.list_businesses(session)
    items = [await _to_public(b) for b in businesses]
    return BusinessListResponse(items=items)


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
    return await _to_public(business)


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
    return await _to_public(business)


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


# --- Logo --------------------------------------------------------------------


@router.post(
    "/{business_id}/logo/upload-session",
    response_model=InitLogoUploadResponse,
    summary="Mint a GCS resumable upload session for a business logo (CEO only)",
)
async def post_init_logo_upload(
    business_id: uuid.UUID,
    body: InitLogoUploadBody,
    request: Request,
    user: Annotated[CurrentUser, Depends(CeoOnly)],
    session: SessionDep,
) -> InitLogoUploadResponse:
    try:
        business = await business_service.get_business(session, business_id=business_id)
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found") from exc
    # GCS resumable-upload quirk: the session URL only echoes CORS headers
    # back to the *origin that minted it*. Without this, the browser sees
    # the PUT succeed at GCS but blocks the response (no Allow-Origin), so
    # the JS upload promise rejects and finalise never fires.
    origin = request.headers.get("origin")
    try:
        session_url, bucket, object_name = await business_service.mint_logo_upload_session(
            business=business,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            origin=origin,
        )
    except business_service.LogoContentTypeNotAllowedError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        ) from exc
    except business_service.LogoTooLargeError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Logo exceeds {business_service.MAX_LOGO_SIZE_BYTES // 1024} KB limit",
        ) from exc
    return InitLogoUploadResponse(
        upload_session_url=session_url,
        gcs_bucket=bucket,
        gcs_object_name=object_name,
    )


@router.post(
    "/{business_id}/logo/finalise",
    response_model=BusinessPublic,
    summary="Attach an uploaded logo to a business (CEO only)",
)
async def post_finalise_logo(
    business_id: uuid.UUID,
    body: FinaliseLogoBody,
    user: Annotated[CurrentUser, Depends(CeoOnly)],
    session: SessionDep,
) -> BusinessPublic:
    try:
        business = await business_service.get_business(session, business_id=business_id)
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found") from exc
    try:
        await business_service.finalise_logo_upload(
            session, business=business, object_name=body.gcs_object_name
        )
    except business_service.LogoBlobMissingError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload not found — finalise after the PUT completes",
        ) from exc
    await session.commit()
    await session.refresh(business)
    return await _to_public(business)


@router.delete(
    "/{business_id}/logo",
    response_model=BusinessPublic,
    summary="Remove a business logo (CEO only)",
)
async def delete_business_logo(
    business_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(CeoOnly)],
    session: SessionDep,
) -> BusinessPublic:
    try:
        business = await business_service.get_business(session, business_id=business_id)
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found") from exc
    await business_service.remove_logo(session, business=business)
    await session.commit()
    await session.refresh(business)
    return await _to_public(business)
