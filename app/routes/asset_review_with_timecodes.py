"""Edit-version endpoints — upload init, finalise, approve, request-changes, playback."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    CurrentUser,
    ProjectAccess,
    SessionDep,
    _user_can_access_project,
    require_project_access,
)
from app.config import get_settings
from sqlalchemy import select

from app.models.edit import EditVersionModel
from app.models.project import ProjectModel
from app.models.user import UserModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.schemas.edit import (
    ALLOWED_CONTENT_TYPES,
    CreateEditBody,
    CreateEditCommentBody,
    EditApprovalPublic,
    EditApprovalSummary,
    EditCommentPublic,
    EditRequiredReviewer,
    EditVersionPublic,
    InitUploadBody,
    InitUploadResponse,
    PlaybackUrlResponse,
    RequestChangesBody,
)
from app.services import edit_service, permission_service, storage_service
from app.services.edit_service import (
    EditCommentNotFoundError,
    EditNotFoundError,
    IllegalEditTransitionError,
    ProjectFinalisedError,
)

log = structlog.get_logger(__name__)

projects_router = APIRouter(prefix="/projects/{project_id}/edits", tags=["edits"])
edits_router = APIRouter(prefix="/edits", tags=["edits"])

# Role gates

# Default playback URL TTL (15 min per spec §11).
PLAYBACK_URL_TTL_SECONDS = 15 * 60


_EXTENSIONS = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
}


def _new_object_name(project_id: uuid.UUID, content_type: str) -> str:
    ext = _EXTENSIONS.get(content_type, "bin")
    return f"projects/{project_id}/edits/{uuid.uuid4()}.{ext}"


@projects_router.post(
    "/init-upload",
    response_model=InitUploadResponse,
    summary="Mint a GCS resumable upload session for a new cut",
)
async def post_init_upload(
    body: InitUploadBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    request: Request,
) -> InitUploadResponse:
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )

    settings = get_settings()
    bucket = settings.gcs_bucket_video
    object_name = _new_object_name(project.id, body.content_type)

    # Pass the request's Origin through so GCS binds the resumable session to
    # this origin AND echoes Access-Control-Allow-Origin on the PUT response.
    # Without this, the upload bytes land in the bucket fine but the browser
    # rejects the response for missing CORS headers, fetch() throws, and the
    # finalize step never fires.
    origin = request.headers.get("origin")

    session_url = await storage_service.create_resumable_upload_session(
        bucket_name=bucket,
        object_name=object_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        origin=origin,
    )
    log.info(
        "edit_upload_init",
        project_id=str(project.id),
        bucket=bucket,
        object_name=object_name,
        size_bytes=body.size_bytes,
        origin=origin,
    )
    return InitUploadResponse(
        upload_session_url=session_url,
        gcs_bucket=bucket,
        gcs_object_name=object_name,
    )


@projects_router.post(
    "",
    response_model=EditVersionPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Finalise an upload and create an edit version",
)
async def post_finalise(
    body: CreateEditBody,
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.EDIT))],
    user: CurrentUser,
    session: SessionDep,
) -> EditVersionPublic:
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Content type {body.content_type!r} not allowed",
        )

    if not await storage_service.blob_exists(
        bucket_name=body.gcs_bucket, object_name=body.gcs_object_name
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload not found in storage — finalise after the PUT completes",
        )

    try:
        edit = await edit_service.add_edit_version(
            session,
            project=project,
            uploader=user,
            gcs_bucket=body.gcs_bucket,
            gcs_object_name=body.gcs_object_name,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            notes=body.notes,
            resolved_comments=body.resolved_comments,
        )
    except ProjectFinalisedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(edit)
    return EditVersionPublic.model_validate(edit)


@projects_router.get(
    "",
    response_model=list[EditVersionPublic],
    summary="List edit versions for a project",
)
async def get_edits(
    project: Annotated[ProjectModel, Depends(require_project_access(ProjectAccess.VIEW))],
    session: SessionDep,
) -> list[EditVersionPublic]:
    edits = await edit_service.list_edits_for_project(session, project_id=project.id)
    return [EditVersionPublic.model_validate(e) for e in edits]


# ---------- single-edit endpoints (no project_id in the path) ----------

async def _project_for_edit(session: AsyncSession, edit: EditVersionModel) -> ProjectModel:
    project_q = await session.execute(
        select(ProjectModel).where(
            ProjectModel.id == edit.project_id,
            ProjectModel.deleted_at.is_(None),
        )
    )
    project = project_q.scalar_one_or_none()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@edits_router.get(
    "/{edit_id}",
    response_model=EditVersionPublic,
    summary="Get one edit version",
)
async def get_edit(
    edit_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> EditVersionPublic:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    return EditVersionPublic.model_validate(edit)


@edits_router.get(
    "/{edit_id}/playback-url",
    response_model=PlaybackUrlResponse,
    summary="Get a short-lived signed playback URL for the cut",
)
async def get_playback_url(
    edit_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> PlaybackUrlResponse:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")

    url = await storage_service.signed_read_url(
        bucket_name=edit.gcs_bucket,
        object_name=edit.gcs_object_name,
        expires_in_seconds=PLAYBACK_URL_TTL_SECONDS,
    )
    return PlaybackUrlResponse(url=url, expires_in_seconds=PLAYBACK_URL_TTL_SECONDS)


@edits_router.post(
    "/{edit_id}/approve",
    response_model=EditVersionPublic,
    summary="Approve a cut (`asset_review_with_timecodes.approve` action)",
)
async def post_approve(
    edit_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> EditVersionPublic:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    # Inline action check — the route path carries `edit_id`, not `project_id`,
    # so `require_action` can't resolve the department without loading the
    # edit first. Check happens after `_project_for_edit` gives us the
    # project (which we also need for the approval handler below).
    allowed = await permission_service.can_user_perform_action(
        session,
        user=user,
        department_id=project.department_id,
        action_key="asset_review_with_timecodes.approve",
        request=request,
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Insufficient permissions to approve cuts"
        )
    try:
        await edit_service.approve_edit(
            session, edit=edit, project=project, actor=user
        )
    except IllegalEditTransitionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ProjectFinalisedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(edit)
    return EditVersionPublic.model_validate(edit)


@edits_router.post(
    "/{edit_id}/request-changes",
    response_model=EditVersionPublic,
    summary="Request changes on a cut (`asset_review_with_timecodes.request_changes` action)",
)
async def post_request_changes(
    edit_id: uuid.UUID,
    body: RequestChangesBody,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> EditVersionPublic:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    allowed = await permission_service.can_user_perform_action(
        session,
        user=user,
        department_id=project.department_id,
        action_key="asset_review_with_timecodes.request_changes",
        request=request,
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Insufficient permissions to request changes",
        )
    try:
        await edit_service.request_changes(
            session, edit=edit, project=project, actor=user, notes=body.notes
        )
    except IllegalEditTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ProjectFinalisedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(edit)
    return EditVersionPublic.model_validate(edit)


@edits_router.get(
    "/{edit_id}/approvals",
    response_model=EditApprovalSummary,
    summary="Get the per-reviewer approval state for one cut",
)
async def get_edit_approvals(
    edit_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> EditApprovalSummary:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    required_ids = await edit_service.required_approver_ids(
        session, project=project
    )
    rows = await edit_service.list_approvals(session, edit_version_id=edit_id)
    # Resolve display info (name + avatar + role label) for every
    # required reviewer — including the ones who haven't approved yet,
    # so the UI can show "Marstark (CEO) · Awaiting" instead of a
    # generic "Pending reviewer" placeholder. The join goes through
    # department_memberships → department_roles inside this dept.
    required_info: list[EditRequiredReviewer] = []
    if required_ids:
        info_rows = await session.execute(
            select(
                UserModel.id,
                UserModel.name,
                UserModel.avatar_url,
                DepartmentRoleModel.name_i18n,
                DepartmentRoleModel.key,
            )
            .join(
                DepartmentMembershipModel,
                DepartmentMembershipModel.user_id == UserModel.id,
            )
            .join(
                DepartmentRoleModel,
                DepartmentRoleModel.id == DepartmentMembershipModel.role_id,
            )
            .where(DepartmentMembershipModel.department_id == project.department_id)
            .where(UserModel.id.in_(required_ids))
        )
        for uid, name, avatar, name_i18n, role_key in info_rows.all():
            role_label = (name_i18n or {}).get("en") or role_key
            required_info.append(
                EditRequiredReviewer(
                    user_id=uid,
                    name=name,
                    avatar_url=avatar,
                    role_label=role_label,
                )
            )
        # CEO super-admin may have no dept membership row — backfill a
        # minimal entry from the users table so they still render with
        # a name (role label falls back to "Approver").
        present = {r.user_id for r in required_info}
        missing_ids = [uid for uid in required_ids if uid not in present]
        if missing_ids:
            user_rows = await session.execute(
                select(UserModel.id, UserModel.name, UserModel.avatar_url).where(
                    UserModel.id.in_(missing_ids)
                )
            )
            for uid, name, avatar in user_rows.all():
                required_info.append(
                    EditRequiredReviewer(
                        user_id=uid,
                        name=name,
                        avatar_url=avatar,
                        role_label="Approver",
                    )
                )

    # Index display info by user_id for approval-row enrichment.
    name_by_id = {r.user_id: (r.name, r.avatar_url) for r in required_info}
    approvals = [
        EditApprovalPublic.model_validate(
            {
                "id": r.id,
                "edit_version_id": r.edit_version_id,
                "reviewer_id": r.reviewer_id,
                "reviewer_name": (
                    name_by_id[r.reviewer_id][0]
                    if r.reviewer_id in name_by_id
                    else None
                ),
                "reviewer_avatar_url": (
                    name_by_id[r.reviewer_id][1]
                    if r.reviewer_id in name_by_id
                    else None
                ),
                "created_at": r.created_at,
            }
        )
        for r in rows
    ]
    can_publish, pending = await edit_service.approval_gate_status(
        session, edit=edit, project=project
    )
    return EditApprovalSummary(
        required_reviewers=required_info,
        approvals=approvals,
        can_publish=can_publish,
        pending_reviewer_ids=pending,
    )


# ---------- timestamped comments on a cut ----------

@edits_router.post(
    "/{edit_id}/comments",
    response_model=EditCommentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Add a timestamped comment to a cut",
)
async def post_edit_comment(
    edit_id: uuid.UUID,
    body: CreateEditCommentBody,
    user: CurrentUser,
    session: SessionDep,
) -> EditCommentPublic:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    try:
        comment = await edit_service.add_edit_comment(
            session,
            edit=edit,
            project=project,
            author=user,
            body=body.body,
            timestamp_seconds=body.timestamp_seconds,
        )
    except ProjectFinalisedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(comment)
    return EditCommentPublic.model_validate(comment)


@edits_router.get(
    "/{edit_id}/comments",
    response_model=list[EditCommentPublic],
    summary="List timestamped comments on a cut",
)
async def get_edit_comments(
    edit_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[EditCommentPublic]:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    comments = await edit_service.list_edit_comments(session, edit_version_id=edit.id)
    # Hide draft comments (sent_at IS NULL) from everyone except their
    # author. The author keeps drafting locally without leaking
    # half-formed feedback to the editor or other reviewers.
    visible = [
        c for c in comments
        if c.sent_at is not None or c.author_id == user.id
    ]
    return [EditCommentPublic.model_validate(c) for c in visible]


@edits_router.post(
    "/{edit_id}/dispatch-comments",
    summary="Send reviewer's draft comments to the editor (stamps sent_at + emails)",
)
async def post_dispatch_comments(
    edit_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    try:
        edit = await edit_service.get_edit(session, edit_id=edit_id)
    except EditNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edit not found") from exc
    project = await _project_for_edit(session, edit)
    if not await _user_can_access_project(session, user, project, ProjectAccess.VIEW):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    try:
        count = await edit_service.dispatch_comments(
            session, edit=edit, project=project, reviewer=user
        )
    except ProjectFinalisedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return {"dispatched": count}


async def _load_edit_comment_and_project(
    session: AsyncSession, comment_id: uuid.UUID
) -> tuple[Any, ProjectModel]:
    try:
        comment = await edit_service.get_edit_comment(session, comment_id=comment_id)
    except EditCommentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found") from exc
    edit_q = await session.execute(
        select(EditVersionModel).where(EditVersionModel.id == comment.edit_version_id)
    )
    edit = edit_q.scalar_one()
    project = await _project_for_edit(session, edit)
    return comment, project


@edits_router.post(
    "/comments/{comment_id}/resolve",
    response_model=EditCommentPublic,
    summary="Mark an edit comment resolved",
)
async def post_resolve_edit_comment(
    comment_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> EditCommentPublic:
    comment, project = await _load_edit_comment_and_project(session, comment_id)
    if not await _user_can_access_project(session, user, project, ProjectAccess.EDIT):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    try:
        await edit_service.resolve_edit_comment(
            session, comment=comment, project=project, actor=user
        )
    except ProjectFinalisedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(comment)
    return EditCommentPublic.model_validate(comment)


@edits_router.post(
    "/comments/{comment_id}/reopen",
    response_model=EditCommentPublic,
    summary="Re-open a resolved edit comment",
)
async def post_reopen_edit_comment(
    comment_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> EditCommentPublic:
    comment, project = await _load_edit_comment_and_project(session, comment_id)
    if not await _user_can_access_project(session, user, project, ProjectAccess.EDIT):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient project access")
    try:
        await edit_service.reopen_edit_comment(
            session, comment=comment, project=project, actor=user
        )
    except ProjectFinalisedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(comment)
    return EditCommentPublic.model_validate(comment)


__all__ = ["edits_router", "projects_router"]
