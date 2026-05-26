"""Business domain service.

Pure business logic — no FastAPI imports. The CEO super-admin can create,
rename, and soft-delete businesses; everyone else just reads the ones they
belong to.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessModel
from app.models.business_membership import BusinessMembershipModel
from app.models.enums import BusinessMembershipStatus
from app.models.user import UserModel

log = structlog.get_logger(__name__)


class BusinessNotFoundError(Exception):
    """Business does not exist or is soft-deleted."""


class SlugTakenError(Exception):
    """Another business already owns this slug."""


class UserNotFoundError(Exception):
    """Email did not match a user on the platform."""


class MembershipAlreadyExistsError(Exception):
    """User already has a membership row for this business."""


_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
_SLUG_TRIM_RE = re.compile(r"^-+|-+$")


def slugify(name: str) -> str:
    """Best-effort kebab-case slug. Caller appends a suffix if it collides."""
    lowered = name.strip().lower()
    slug = _SLUG_STRIP_RE.sub("-", lowered)
    slug = _SLUG_TRIM_RE.sub("", slug)
    return slug or "business"


async def _slug_is_taken(session: AsyncSession, slug: str) -> bool:
    result = await session.execute(
        select(BusinessModel.id).where(BusinessModel.slug == slug)
    )
    return result.first() is not None


async def create_business(
    session: AsyncSession,
    *,
    actor: UserModel,
    name: str,
    slug: str | None = None,
) -> BusinessModel:
    """Create a business owned by `actor`. Auto-suffixes the slug on collision."""
    base_slug = slug or slugify(name)
    candidate = base_slug
    counter = 1
    while await _slug_is_taken(session, candidate):
        counter += 1
        candidate = f"{base_slug}-{counter}"

    business = BusinessModel(
        name=name,
        slug=candidate,
        owner_user_id=actor.id,
    )
    session.add(business)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise SlugTakenError(candidate) from exc

    # Owner gets an active membership so list/me/businesses works the same
    # for the owner as for any other member (the CEO bypass is orthogonal).
    membership = BusinessMembershipModel(
        business_id=business.id,
        user_id=actor.id,
        status=BusinessMembershipStatus.ACTIVE,
        invited_by=actor.id,
        joined_at=datetime.now(UTC),
    )
    session.add(membership)
    await session.flush()
    return business


async def list_businesses(session: AsyncSession) -> Sequence[BusinessModel]:
    """Return every non-deleted business — RLS narrows for non-CEO callers."""
    result = await session.execute(
        select(BusinessModel)
        .where(BusinessModel.deleted_at.is_(None))
        .order_by(BusinessModel.created_at.asc())
    )
    return result.scalars().all()


async def get_business(
    session: AsyncSession, *, business_id: uuid.UUID
) -> BusinessModel:
    result = await session.execute(
        select(BusinessModel).where(
            BusinessModel.id == business_id,
            BusinessModel.deleted_at.is_(None),
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise BusinessNotFoundError(str(business_id))
    return business


async def update_business(
    session: AsyncSession,
    *,
    business: BusinessModel,
    name: str | None = None,
    slug: str | None = None,
) -> BusinessModel:
    if name is not None and name != business.name:
        business.name = name
    if slug is not None and slug != business.slug:
        if await _slug_is_taken(session, slug):
            raise SlugTakenError(slug)
        business.slug = slug
    await session.flush()
    return business


async def soft_delete_business(
    session: AsyncSession, *, business: BusinessModel
) -> BusinessModel:
    if business.deleted_at is None:
        business.deleted_at = datetime.now(UTC)
        await session.flush()
    return business


# --- Logo --------------------------------------------------------------------

ALLOWED_LOGO_CONTENT_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024
LOGO_URL_TTL_SECONDS = 15 * 60


class LogoContentTypeNotAllowedError(Exception):
    """Caller asked to upload a logo with an unsupported MIME type."""


class LogoTooLargeError(Exception):
    """Declared upload size exceeds MAX_LOGO_SIZE_BYTES."""


class LogoBlobMissingError(Exception):
    """Caller tried to finalise a logo before the GCS PUT completed."""


def _logo_object_name(business_id: uuid.UUID, content_type: str) -> str:
    """Stable per-upload object key.

    A UUID suffix means each upload writes to a new key — previous logos
    become orphans but the browser-cached signed URL of the old key keeps
    working until expiry, so no flash-of-broken-image during swap.
    """
    ext = ALLOWED_LOGO_CONTENT_TYPES[content_type]
    return f"businesses/{business_id}/logo-{uuid.uuid4()}{ext}"


async def mint_logo_upload_session(
    *,
    business: BusinessModel,
    content_type: str,
    size_bytes: int,
    origin: str | None = None,
) -> tuple[str, str, str]:
    """Return (session_url, bucket, object_name) for a logo upload."""
    if content_type not in ALLOWED_LOGO_CONTENT_TYPES:
        raise LogoContentTypeNotAllowedError(content_type)
    if size_bytes > MAX_LOGO_SIZE_BYTES:
        raise LogoTooLargeError(str(size_bytes))

    from app.config import get_settings
    from app.services import storage_service

    bucket = get_settings().gcs_bucket_assets
    object_name = _logo_object_name(business.id, content_type)
    session_url = await storage_service.create_resumable_upload_session(
        bucket_name=bucket,
        object_name=object_name,
        content_type=content_type,
        size_bytes=size_bytes,
        origin=origin,
    )
    return session_url, bucket, object_name


async def finalise_logo_upload(
    session: AsyncSession,
    *,
    business: BusinessModel,
    object_name: str,
) -> BusinessModel:
    """Verify the GCS blob exists, then point the business at it."""
    from app.config import get_settings
    from app.services import storage_service

    bucket = get_settings().gcs_bucket_assets
    if not await storage_service.blob_exists(
        bucket_name=bucket, object_name=object_name
    ):
        raise LogoBlobMissingError(object_name)
    business.logo_object_name = object_name
    await session.flush()
    return business


async def remove_logo(
    session: AsyncSession, *, business: BusinessModel
) -> BusinessModel:
    """Clear the logo pointer. The orphan blob is left to lifecycle rules."""
    if business.logo_object_name is not None:
        business.logo_object_name = None
        await session.flush()
    return business


async def build_signed_logo_url(business: BusinessModel) -> str | None:
    """Mint a short-lived signed read URL for the business logo, if any."""
    if business.logo_object_name is None:
        return None
    from app.config import get_settings
    from app.services import storage_service

    bucket = get_settings().gcs_bucket_assets
    return await storage_service.signed_read_url(
        bucket_name=bucket,
        object_name=business.logo_object_name,
        expires_in_seconds=LOGO_URL_TTL_SECONDS,
        response_content_disposition="inline",
    )


# --- Memberships -------------------------------------------------------------


async def list_memberships(
    session: AsyncSession, *, business_id: uuid.UUID
) -> Sequence[BusinessMembershipModel]:
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(BusinessMembershipModel)
        .options(selectinload(BusinessMembershipModel.user))
        .where(BusinessMembershipModel.business_id == business_id)
        .order_by(BusinessMembershipModel.created_at.asc())
    )
    return result.scalars().all()


async def invite_member_by_email(
    session: AsyncSession,
    *,
    business: BusinessModel,
    actor: UserModel,
    email: str,
) -> BusinessMembershipModel:
    """Add an existing platform user to a business as an active member.

    The user must already exist on the platform — platform-level invitation
    (via the NextAuth Team page) is the prerequisite. This endpoint only
    adds them to a specific business.
    """
    normalised = email.strip().lower()
    result = await session.execute(
        select(UserModel).where(
            UserModel.email == normalised, UserModel.deleted_at.is_(None)
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(normalised)

    existing = await session.execute(
        select(BusinessMembershipModel).where(
            BusinessMembershipModel.business_id == business.id,
            BusinessMembershipModel.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise MembershipAlreadyExistsError(f"{user.id} in {business.id}")

    membership = BusinessMembershipModel(
        business_id=business.id,
        user_id=user.id,
        status=BusinessMembershipStatus.ACTIVE,
        invited_by=actor.id,
        joined_at=datetime.now(UTC),
    )
    # Pre-attach the user we already have in hand so the
    # `lazy="raise"` relationship is satisfied without an extra query
    # when the route serialises the freshly-created membership.
    membership.user = user
    session.add(membership)
    await session.flush()
    return membership


class CannotRevokeCeoError(Exception):
    """Raised when a caller tries to revoke the CEO's business membership.

    The CEO is the platform super-admin; they bypass RLS and must be a member
    of every business by definition. Revoking would orphan the business.
    """


async def revoke_membership(
    session: AsyncSession, *, membership_id: uuid.UUID, business_id: uuid.UUID
) -> None:
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(BusinessMembershipModel)
        .options(selectinload(BusinessMembershipModel.user))
        .where(
            BusinessMembershipModel.id == membership_id,
            BusinessMembershipModel.business_id == business_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise BusinessNotFoundError(f"membership {membership_id}")
    if membership.user.is_super_admin:
        raise CannotRevokeCeoError(str(membership.user_id))
    await session.delete(membership)
    await session.flush()


async def set_business_membership_status(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    membership_id: uuid.UUID,
    status: BusinessMembershipStatus,
) -> BusinessMembershipModel:
    """Flip a business membership's status (soft enable/disable).

    Unlike `revoke_membership` (which deletes the row), this preserves the
    membership row and just toggles `status` between ACTIVE and REVOKED.
    The middleware's `_user_is_active_member` only lets ACTIVE through, so
    a REVOKED user is blocked from the business without losing their
    department role assignments or history.
    """
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(BusinessMembershipModel)
        .options(selectinload(BusinessMembershipModel.user))
        .where(
            BusinessMembershipModel.id == membership_id,
            BusinessMembershipModel.business_id == business_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise BusinessNotFoundError(f"membership {membership_id}")
    if membership.user.is_super_admin and status != BusinessMembershipStatus.ACTIVE:
        raise CannotRevokeCeoError(str(membership.user_id))
    membership.status = status
    if status == BusinessMembershipStatus.ACTIVE and membership.joined_at is None:
        membership.joined_at = datetime.now(UTC)
    await session.flush()
    # `TimestampMixin.updated_at` carries a server-side `onupdate=NOW()`.
    # SQLAlchemy can't know the DB-written value so it expires the
    # attribute post-flush; the next attribute access (Pydantic
    # serialisation) would lazy-load and raise MissingGreenlet inside
    # the async response cycle. Refresh just that column to pre-load it.
    await session.refresh(membership, attribute_names=["updated_at"])
    return membership


__all__ = [
    "ALLOWED_LOGO_CONTENT_TYPES",
    "LOGO_URL_TTL_SECONDS",
    "MAX_LOGO_SIZE_BYTES",
    "BusinessNotFoundError",
    "CannotRevokeCeoError",
    "LogoBlobMissingError",
    "LogoContentTypeNotAllowedError",
    "LogoTooLargeError",
    "MembershipAlreadyExistsError",
    "SlugTakenError",
    "UserNotFoundError",
    "build_signed_logo_url",
    "create_business",
    "finalise_logo_upload",
    "get_business",
    "invite_member_by_email",
    "list_businesses",
    "list_memberships",
    "mint_logo_upload_session",
    "remove_logo",
    "revoke_membership",
    "set_business_membership_status",
    "slugify",
    "soft_delete_business",
    "update_business",
]
