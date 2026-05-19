"""Permissions matrix tests (Phase 1 Task 1.4.6).

Unit tests for the pure helpers `_user_can_access_project` and
`can_user_move_to_stage`. End-to-end role-vs-endpoint tests land in
`test_projects.py` once Task 1.5's routes exist.
"""

from __future__ import annotations

import uuid

import pytest

from app.auth.dependencies import (
    ProjectAccess,
    _user_can_access_project,
    can_user_move_to_stage,
)
from app.models.enums import Category, PipelineStage, Role
from app.models.project import ProjectModel
from app.models.user import UserModel


def _make_user(role: Role, user_id: uuid.UUID | None = None) -> UserModel:
    user = UserModel(
        email=f"{role.value}@example.com",
        name=role.value,
        role=role,
        locale="nl",
    )
    user.id = user_id or uuid.uuid4()
    return user


def _make_project(owner_id: uuid.UUID, stage: PipelineStage = PipelineStage.IDEA) -> ProjectModel:
    project = ProjectModel(
        title="t",
        category=Category.PROPERTY_TOUR,
        stage=stage,
        owner_id=owner_id,
    )
    project.id = uuid.uuid4()
    return project


# ---------- project access matrix ----------

@pytest.mark.parametrize(
    ("role", "is_owner", "level", "expected"),
    [
        # CEO sees + edits + manages everything
        (Role.CEO, False, ProjectAccess.VIEW, True),
        (Role.CEO, False, ProjectAccess.EDIT, True),
        (Role.CEO, False, ProjectAccess.MANAGE, True),
        # Assistant Director: full edit + manage on any project, view always
        (Role.ASSISTANT_DIRECTOR, False, ProjectAccess.VIEW, True),
        (Role.ASSISTANT_DIRECTOR, False, ProjectAccess.EDIT, True),
        (Role.ASSISTANT_DIRECTOR, False, ProjectAccess.MANAGE, True),
        # Junior Director: only on owned projects
        (Role.JUNIOR_DIRECTOR, True, ProjectAccess.EDIT, True),
        (Role.JUNIOR_DIRECTOR, False, ProjectAccess.EDIT, False),
        (Role.JUNIOR_DIRECTOR, True, ProjectAccess.MANAGE, True),
        (Role.JUNIOR_DIRECTOR, False, ProjectAccess.MANAGE, False),
        (Role.JUNIOR_DIRECTOR, False, ProjectAccess.VIEW, True),  # views all
        # Editor: edits owned, views all, can't manage
        (Role.EDITOR, True, ProjectAccess.EDIT, True),
        (Role.EDITOR, False, ProjectAccess.EDIT, False),
        (Role.EDITOR, True, ProjectAccess.MANAGE, False),
        (Role.EDITOR, False, ProjectAccess.VIEW, True),
        # Crew: only views assigned project (proxied by ownership)
        (Role.CREW, True, ProjectAccess.VIEW, True),
        (Role.CREW, False, ProjectAccess.VIEW, False),
        (Role.CREW, True, ProjectAccess.EDIT, False),
        # Viewer: read-only
        (Role.VIEWER, False, ProjectAccess.VIEW, True),
        (Role.VIEWER, True, ProjectAccess.EDIT, False),
        (Role.VIEWER, True, ProjectAccess.MANAGE, False),
    ],
)
def test_user_can_access_project_matrix(
    role: Role, is_owner: bool, level: ProjectAccess, expected: bool
) -> None:
    user = _make_user(role)
    owner_id = user.id if is_owner else uuid.uuid4()
    project = _make_project(owner_id)
    assert _user_can_access_project(user, project, level) is expected


# ---------- stage-move matrix ----------

@pytest.mark.parametrize(
    ("role", "is_owner", "stage", "expected"),
    [
        # CEO always
        (Role.CEO, False, PipelineStage.SCRIPT_REVIEW, True),
        (Role.CEO, False, PipelineStage.APPROVED_PUBLISHED, True),
        # Asst Dir: any stage except publish (publish is CEO-only)
        (Role.ASSISTANT_DIRECTOR, False, PipelineStage.EDITING, True),
        (Role.ASSISTANT_DIRECTOR, False, PipelineStage.APPROVED_PUBLISHED, False),
        # Jr Dir: only owned, never publish
        (Role.JUNIOR_DIRECTOR, True, PipelineStage.SCRIPT_LOCKED, True),
        (Role.JUNIOR_DIRECTOR, False, PipelineStage.SCRIPT_LOCKED, False),
        (Role.JUNIOR_DIRECTOR, True, PipelineStage.APPROVED_PUBLISHED, False),
        # Editor / Crew / Viewer: never
        (Role.EDITOR, True, PipelineStage.EDITING, False),
        (Role.CREW, True, PipelineStage.SHOOT_DONE, False),
        (Role.VIEWER, True, PipelineStage.IDEA, False),
    ],
)
def test_can_user_move_to_stage_matrix(
    role: Role, is_owner: bool, stage: PipelineStage, expected: bool
) -> None:
    user = _make_user(role)
    owner_id = user.id if is_owner else uuid.uuid4()
    project = _make_project(owner_id)
    assert can_user_move_to_stage(user, project, stage) is expected
