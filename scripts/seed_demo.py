"""Idempotent bootstrap seed — CEO + Sons Real Estate + Content Creation.

What this seeds (in order, idempotently):

  1. The CEO user — `CEO_EMAIL` / `CEO_NAME` / `CEO_INITIAL_PASSWORD` from `.env.local`.
     Marked `must_change_password=True` so first login forces `/change-password`.
  2. The **Sons Real Estate** business, owned by the CEO + a matching
     `business_memberships` row so `/me/businesses` works.
  3. The **Content Creation** department under Sons Real Estate, instantiated
     from the `content_creation` template (which Phase B's migration upserts
     into `department_templates` regardless of seed state). Picks up 11 stages,
     6 roles, 67 permission triples, 5 capabilities, and the per-capability
     config for `participant_roster` (`kind="cast"`).
  4. The CEO's `department_memberships` row mapping them to the department's
     `ceo` role.

**No demo projects** — the kanban is intentionally empty on first login so
testing starts from a clean slate. Create projects via the UI.

Re-running is safe — every step is upsert / lookup-or-create. Change
`CEO_INITIAL_PASSWORD` in `.env.local` and re-run; the bcrypt hash refreshes.

Run via `make seed` or `uv run python scripts/seed_demo.py`.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Make the repo root importable when run as `python scripts/seed_demo.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.models.base import dispose_engine, get_sessionmaker
from app.models.business import BusinessModel
from app.models.business_membership import BusinessMembershipModel
from app.models.department import DepartmentModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.enums import BusinessMembershipStatus, Role
from app.models.user import UserModel
from app.services import department_service

log = structlog.get_logger(__name__)

# Bcrypt's OpenBSD impl caps password at 72 bytes. Same constraint applies on
# the Next.js side (bcryptjs) — they produce cross-runtime-compatible hashes.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

SONS_RE_NAME = "Sons Real Estate"
SONS_RE_SLUG = "sons-real-estate"
CONTENT_CREATION_NAME = "Content Creation"
CONTENT_CREATION_TEMPLATE_KEY = "content_creation"


def _hash_password(plain: str) -> str:
    raw = plain.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise SystemExit(
            f"CEO_INITIAL_PASSWORD is longer than {MAX_PASSWORD_BYTES} UTF-8 bytes (bcrypt cap)."
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def _require_ceo_settings(settings: Settings) -> tuple[str, str, str]:
    if not settings.ceo_initial_password:
        raise SystemExit(
            "CEO_INITIAL_PASSWORD is not set. Add it to .env.local before running `make seed`."
        )
    if len(settings.ceo_initial_password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"CEO_INITIAL_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    return settings.ceo_email, settings.ceo_name, settings.ceo_initial_password


async def _upsert_ceo(
    session: AsyncSession, *, email: str, name: str, password_hash: str
) -> UserModel:
    """Idempotent: if the CEO row exists, refresh name + password hash."""
    now = datetime.now(UTC)
    result = await session.execute(select(UserModel).where(UserModel.email == email))
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.name = name
        existing.role = Role.CEO
        existing.password_hash = password_hash
        existing.must_change_password = True
        existing.accepted_at = existing.accepted_at or now
        log.info("seed_ceo_refreshed", email=email)
        await session.flush()
        return existing

    user = UserModel(
        email=email,
        name=name,
        role=Role.CEO,
        locale="nl",
        password_hash=password_hash,
        must_change_password=True,
        accepted_at=now,
    )
    session.add(user)
    await session.flush()
    log.info("seed_ceo_created", email=email)
    return user


async def _upsert_sons_re(session: AsyncSession, ceo: UserModel) -> BusinessModel:
    """Look up the Sons Real Estate business by slug; create if absent.

    Also ensures the CEO has an `active` `business_memberships` row so
    `GET /me/businesses` returns Sons RE for them. CEOs are super-admins
    and can act on any business regardless, but the membership row makes
    the topbar switcher behave consistently with regular members.
    """
    result = await session.execute(
        select(BusinessModel).where(BusinessModel.slug == SONS_RE_SLUG)
    )
    business = result.scalar_one_or_none()
    if business is None:
        business = BusinessModel(
            name=SONS_RE_NAME, slug=SONS_RE_SLUG, owner_user_id=ceo.id
        )
        session.add(business)
        await session.flush()
        log.info("seed_business_created", slug=SONS_RE_SLUG)
    else:
        log.info("seed_business_exists", slug=SONS_RE_SLUG)

    # Idempotent CEO membership.
    membership_q = await session.execute(
        select(BusinessMembershipModel).where(
            BusinessMembershipModel.business_id == business.id,
            BusinessMembershipModel.user_id == ceo.id,
        )
    )
    if membership_q.scalar_one_or_none() is None:
        session.add(
            BusinessMembershipModel(
                business_id=business.id,
                user_id=ceo.id,
                status=BusinessMembershipStatus.ACTIVE,
                joined_at=datetime.now(UTC),
            )
        )
        await session.flush()
        log.info("seed_business_membership_created", slug=SONS_RE_SLUG)
    return business


async def _ensure_content_creation_dept(
    session: AsyncSession, business: BusinessModel, ceo: UserModel
) -> DepartmentModel:
    """Look up the Content Creation department under Sons RE; if absent,
    instantiate it from the `content_creation` template.

    Also ensures the CEO has a `department_memberships` row mapping them to
    the department's `ceo` role so the kanban + permissions UI behave
    correctly under the per-department role model.
    """
    result = await session.execute(
        select(DepartmentModel).where(
            DepartmentModel.business_id == business.id,
            DepartmentModel.slug == "content-creation",
        )
    )
    dept = result.scalar_one_or_none()
    if dept is None:
        dept = await department_service.create_department(
            session,
            business_id=business.id,
            name=CONTENT_CREATION_NAME,
            template_key=CONTENT_CREATION_TEMPLATE_KEY,
        )
        log.info("seed_department_created", slug=dept.slug)
    else:
        log.info("seed_department_exists", slug=dept.slug)

    # CEO membership in the department, mapped to the `ceo` role.
    role_q = await session.execute(
        select(DepartmentRoleModel).where(
            DepartmentRoleModel.department_id == dept.id,
            DepartmentRoleModel.key == "ceo",
        )
    )
    ceo_role = role_q.scalar_one_or_none()
    if ceo_role is None:
        log.warning(
            "seed_ceo_role_missing",
            department_id=str(dept.id),
            hint="Template instantiation should have created a 'ceo' role; check the template definition.",
        )
        return dept

    membership_q = await session.execute(
        select(DepartmentMembershipModel).where(
            DepartmentMembershipModel.department_id == dept.id,
            DepartmentMembershipModel.user_id == ceo.id,
        )
    )
    if membership_q.scalar_one_or_none() is None:
        await department_service.assign_department_member(
            session, department=dept, user_id=ceo.id, role_id=ceo_role.id
        )
        log.info("seed_department_membership_created", slug=dept.slug)
    return dept


async def _run() -> None:
    settings = get_settings()
    email, name, password = _require_ceo_settings(settings)
    password_hash = _hash_password(password)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        ceo = await _upsert_ceo(
            session, email=email, name=name, password_hash=password_hash
        )
        business = await _upsert_sons_re(session, ceo)
        await _ensure_content_creation_dept(session, business, ceo)
        await session.commit()
    await dispose_engine()


def main() -> None:
    configure_logging(get_settings())
    asyncio.run(_run())
    log.info("seed_complete")


if __name__ == "__main__":
    main()
