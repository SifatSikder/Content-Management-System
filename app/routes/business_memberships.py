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
    await session.commit()
    # `lazy="raise"` on BusinessMembershipModel.user means the default
    # refresh would explode when serialisation accesses `.user`. Include
    # the relation in the refresh so the response carries the joined user.
    await session.refresh(membership, attribute_names=["user"])
    return BusinessMembershipPublic.model_validate(membership)


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
