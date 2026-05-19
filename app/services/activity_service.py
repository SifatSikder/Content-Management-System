"""Activity-log writer + reader.

Every mutating endpoint should call `record()` from inside the same DB session
so the audit row commits with the mutation. `list_for_project` is the read
side, used by the activity-feed endpoint.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityModel

log = structlog.get_logger(__name__)

DEFAULT_ACTIVITY_PAGE_SIZE = 50
MAX_ACTIVITY_PAGE_SIZE = 200


class InvalidActivityCursorError(Exception):
    """Pagination cursor failed to decode."""


def _encode_cursor(row: ActivityModel) -> str:
    raw = f"{row.created_at.isoformat()}|{row.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        iso, id_str = raw.split("|", 1)
        return datetime.fromisoformat(iso), uuid.UUID(id_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidActivityCursorError(f"Invalid cursor: {cursor!r}") from exc


async def record(
    session: AsyncSession,
    *,
    project_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str,
    metadata: dict[str, Any] | None = None,
) -> ActivityModel:
    """Append an activity row to the given session.

    Caller commits. `action` is a verb-style key (`project.created`,
    `project.stage_changed`, `script.locked`, …). `metadata` is freeform
    JSONB — keep keys short and stable, no PII.
    """
    entry = ActivityModel(
        project_id=project_id,
        actor_id=actor_id,
        action=action,
        metadata_json=metadata or {},
    )
    session.add(entry)
    await session.flush()
    log.info(
        "activity_logged",
        project_id=str(project_id) if project_id else None,
        actor_id=str(actor_id) if actor_id else None,
        action=action,
    )
    return entry


async def list_for_project(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = DEFAULT_ACTIVITY_PAGE_SIZE,
) -> tuple[Sequence[ActivityModel], str | None]:
    """Paginated activity feed (most-recent first) for a single project."""
    limit = max(1, min(limit, MAX_ACTIVITY_PAGE_SIZE))

    query = (
        select(ActivityModel)
        .where(ActivityModel.project_id == project_id)
        .order_by(ActivityModel.created_at.desc(), ActivityModel.id.desc())
    )

    if cursor is not None:
        cursor_ts, cursor_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                ActivityModel.created_at < cursor_ts,
                and_(
                    ActivityModel.created_at == cursor_ts,
                    ActivityModel.id < cursor_id,
                ),
            )
        )

    query = query.limit(limit + 1)
    result = await session.execute(query)
    rows = list(result.scalars().all())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _encode_cursor(rows[-1])

    return rows, next_cursor


__all__ = [
    "DEFAULT_ACTIVITY_PAGE_SIZE",
    "MAX_ACTIVITY_PAGE_SIZE",
    "InvalidActivityCursorError",
    "list_for_project",
    "record",
]
