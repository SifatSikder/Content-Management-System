"""Business membership endpoints.

Listing requires plain business membership. Mutating (invite, revoke)
requires CEO or the business's owner via `require_business_admin`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import (
    CurrentUser,
    SessionDep,
    require_business_admin,
    require_business_member,
)
from app.models.business import BusinessModel
from app.schemas.business import (
    BusinessMembershipListResponse,
    BusinessMembershipPublic,
    InviteBusinessMemberBody,
    UpdateBusinessMembershipBody,
)
from app.services import business_service

router = APIRouter(prefix="/businesses", tags=["business-memberships"])
log = structlog.get_logger(__name__)


@router.get(
    "/{business_id}/memberships",
    response_model=BusinessMembershipListResponse,
    summary="List a business's memberships",
)
async def get_memberships(
    business_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    _: Annotated[object, Depends(require_business_member)],
) -> BusinessMembershipListResponse:
    rows = await business_service.list_memberships(session, business_id=business_id)
    return BusinessMembershipListResponse(
        items=[BusinessMembershipPublic.model_validate(r) for r in rows]
    )


@router.post(
    "/{business_id}/memberships",
    response_model=BusinessMembershipPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Invite an existing platform user into the business",
)
async def post_membership(
    body: InviteBusinessMemberBody,
    user: CurrentUser,
    session: SessionDep,
    business: Annotated[BusinessModel, Depends(require_business_admin)],
) -> BusinessMembershipPublic:
    try:
        membership = await business_service.invite_member_by_email(
            session, business=business, actor=user, email=body.email
        )
    except business_service.UserNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No user with that email on the platform — invite via the Team page first",
        ) from exc
    except business_service.MembershipAlreadyExistsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "User is already a member of this business",
        ) from exc
    # Validate-before-commit: post-commit the row's columns are expired
    # and lazy-loading them mid-serialisation raises MissingGreenlet.
    # `user` is already eager-loaded inside the service.
    response = BusinessMembershipPublic.model_validate(membership)
    await session.commit()
    return response


@router.patch(
    "/{business_id}/memberships/{membership_id}",
    response_model=BusinessMembershipPublic,
    summary="Toggle a business membership between active and revoked (soft-disable)",
)
async def patch_membership(
    business_id: uuid.UUID,
    membership_id: uuid.UUID,
    body: UpdateBusinessMembershipBody,
    user: CurrentUser,
    session: SessionDep,
    _: Annotated[BusinessModel, Depends(require_business_admin)],
) -> BusinessMembershipPublic:
    """Flip a member between active (full access) and inactive (revoked,
    blocked at the business gate but with department roles preserved).

    The CEO row can't be set to anything other than ACTIVE — flipping
    them off would orphan the platform.
    """
    try:
        membership = await business_service.set_business_membership_status(
            session,
            business_id=business_id,
            membership_id=membership_id,
            status=body.status,
        )
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found") from exc
    except business_service.CannotRevokeCeoError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The CEO's membership cannot be revoked"
        ) from exc
    # Construct the response BEFORE commit. After commit the session
    # expires all attributes; a subsequent refresh with `attribute_names`
    # only reloads the named ones, leaving the rest in lazy-IO state —
    # which raises MissingGreenlet inside the async serialiser.
    response = BusinessMembershipPublic.model_validate(membership)
    await session.commit()
    return response


@router.delete(
    "/{business_id}/memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a business membership",
)
async def delete_membership(
    business_id: uuid.UUID,
    membership_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    _: Annotated[BusinessModel, Depends(require_business_admin)],
) -> None:
    try:
        await business_service.revoke_membership(
            session, membership_id=membership_id, business_id=business_id
        )
    except business_service.BusinessNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found") from exc
    except business_service.CannotRevokeCeoError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The CEO's membership cannot be revoked"
        ) from exc
    await session.commit()
