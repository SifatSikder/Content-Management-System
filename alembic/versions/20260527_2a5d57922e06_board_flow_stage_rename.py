"""Phase 1 of board-flow rework: rename + reorder content_creation stages.

Revision ID: 2a5d57922e06
Revises: a1b9d3e7c5f2
Create Date: 2026-05-27 11:30:00.000000

Reshape the Content Creation pipeline to match how the team actually works:

  location_scouting -> draft_idea -> script_drafting -> script_review ->
  casting -> shoot_schedule -> shoot_in_progress -> shoot_done ->
  editing -> edit_review -> approved_published

Specifically:
  - `idea` renamed to `draft_idea`.
  - `script_locked` removed as a stage; locking is a project property
    (`script_locked_at` / `script_locked_by`). Any project currently sitting
    on `script_locked` is jumped to `script_drafting` (the lock columns
    survive, so the UI keeps rendering the "locked" badge).
  - `shoot_scheduled` renamed to `shoot_schedule`.
  - `shoot_in_progress` added between `shoot_schedule` and `shoot_done`.
  - `final_review` renamed to `edit_review`.
  - `location_scouting` becomes the FIRST stage (was: idea).

For existing Content Creation departments, every `stage.move:<a>-><b>`
permission row is rewritten in lockstep:
  - source/target key renames applied,
  - any row that still references `script_locked` is dropped,
  - any row whose (from, to) is no longer in the new transition graph is
    dropped,
  - the new transitions (`location_scouting->draft_idea`,
    `script_drafting->casting`, `script_review->casting`,
    `shoot_schedule->shoot_in_progress`, `shoot_in_progress->shoot_done`)
    are inserted for the CEO + Assistant-Director + Junior-Director role
    keys when those roles exist in the department.

Non-`stage.move` action keys (project.create, script_versioning.lock, etc.)
are untouched.

Down-revision rebuilds the old graph. Projects on `shoot_in_progress` are
demoted to `shoot_schedule` (lossy — the in-progress detail lives in
`shoots.status`, which is unaffected).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2a5d57922e06"
down_revision: Union[str, Sequence[str], None] = "a1b9d3e7c5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ----- stage rename mapping ------------------------------------------------

# Applied to `projects.stage_key` and (with the `stage.move:` prefix) to
# `department_role_permissions.action_key`.
STAGE_RENAMES_FWD: list[tuple[str, str]] = [
    ("idea", "draft_idea"),
    ("script_locked", "script_drafting"),
    ("shoot_scheduled", "shoot_schedule"),
    ("final_review", "edit_review"),
]
STAGE_RENAMES_BWD: list[tuple[str, str]] = [
    ("draft_idea", "idea"),
    # On downgrade we cannot perfectly reconstruct which `script_drafting`
    # rows were previously `script_locked`; the `script_locked_at` column
    # gives us a reliable proxy.
    ("shoot_schedule", "shoot_scheduled"),
    ("edit_review", "final_review"),
]

# New transition graph (after Phase 1). Used to (a) prune obsolete permission
# rows, (b) seed the brand-new transitions for existing departments.
NEW_TRANSITIONS: list[tuple[str, str]] = [
    ("location_scouting", "draft_idea"),
    ("draft_idea", "script_drafting"),
    ("script_drafting", "script_review"),
    ("script_review", "script_drafting"),
    ("script_drafting", "casting"),
    ("script_review", "casting"),
    ("casting", "shoot_schedule"),
    ("shoot_schedule", "shoot_in_progress"),
    ("shoot_in_progress", "shoot_done"),
    ("shoot_done", "editing"),
    ("editing", "edit_review"),
    ("edit_review", "editing"),
    ("edit_review", "approved_published"),
    ("editing", "approved_published"),
]

PUBLISH_TRANSITIONS: set[tuple[str, str]] = {
    ("edit_review", "approved_published"),
    ("editing", "approved_published"),
}

# Old transition graph (before Phase 1). Used by the downgrade.
OLD_TRANSITIONS: list[tuple[str, str]] = [
    ("idea", "script_drafting"),
    ("script_drafting", "script_review"),
    ("script_drafting", "script_locked"),
    ("script_review", "script_locked"),
    ("script_locked", "script_review"),
    ("idea", "location_scouting"),
    ("script_drafting", "location_scouting"),
    ("script_review", "location_scouting"),
    ("script_locked", "location_scouting"),
    ("location_scouting", "casting"),
    ("casting", "shoot_scheduled"),
    ("shoot_scheduled", "shoot_done"),
    ("shoot_done", "editing"),
    ("editing", "final_review"),
    ("final_review", "editing"),
    ("final_review", "approved_published"),
    ("editing", "approved_published"),
]
OLD_PUBLISH: set[tuple[str, str]] = {
    ("final_review", "approved_published"),
    ("editing", "approved_published"),
}


def _move_key(frm: str, to: str) -> str:
    return f"stage.move:{frm}->{to}"


# ----- upgrade -------------------------------------------------------------


CC_DEPT_FILTER = """
    EXISTS (
        SELECT 1
        FROM departments d
        JOIN department_roles r ON r.department_id = d.id
        WHERE r.id = department_role_permissions.department_role_id
          AND d.template_key = 'content_creation'
    )
"""


def _rename_action_keys(bind: sa.engine.Connection, old: str, new: str) -> None:
    """Rewrite `stage.move:<old>-><X>` and `stage.move:<X>-><old>` to use
    `<new>` in CC departments, deleting any row that would self-loop or
    collide with an existing row on the same role before the rename."""

    # Source-side: pre-delete rows where the renamed action_key would be a
    # self-loop OR would collide with an existing row on the same role.
    bind.execute(
        sa.text(
            f"""
            DELETE FROM department_role_permissions
            WHERE action_key LIKE 'stage.move:' || :old || '->%'
              AND (
                substring(action_key from char_length('stage.move:' || :old || '->') + 1) = :new
                OR EXISTS (
                    SELECT 1 FROM department_role_permissions b
                    WHERE b.department_role_id = department_role_permissions.department_role_id
                      AND b.action_key = 'stage.move:' || :new || '->' || substring(
                          department_role_permissions.action_key
                          from char_length('stage.move:' || :old || '->') + 1
                      )
                )
              )
              AND {CC_DEPT_FILTER}
            """
        ),
        {"old": old, "new": new},
    )
    # Source-side rename.
    bind.execute(
        sa.text(
            f"""
            UPDATE department_role_permissions
            SET action_key = 'stage.move:' || :new || '->' || substring(
                action_key from char_length('stage.move:' || :old || '->') + 1
            )
            WHERE action_key LIKE 'stage.move:' || :old || '->%'
              AND {CC_DEPT_FILTER}
            """
        ),
        {"old": old, "new": new},
    )

    # Target-side: pre-delete rows where the renamed action_key would be a
    # self-loop OR would collide.
    bind.execute(
        sa.text(
            f"""
            DELETE FROM department_role_permissions
            WHERE action_key LIKE 'stage.move:%->' || :old
              AND (
                substring(
                    action_key
                    from char_length('stage.move:') + 1
                    for char_length(action_key) - char_length('stage.move:->' || :old)
                ) = :new
                OR EXISTS (
                    SELECT 1 FROM department_role_permissions b
                    WHERE b.department_role_id = department_role_permissions.department_role_id
                      AND b.action_key = 'stage.move:' || substring(
                          department_role_permissions.action_key
                          from char_length('stage.move:') + 1
                          for char_length(department_role_permissions.action_key) - char_length('stage.move:->' || :old)
                      ) || '->' || :new
                )
              )
              AND {CC_DEPT_FILTER}
            """
        ),
        {"old": old, "new": new},
    )
    # Target-side rename.
    bind.execute(
        sa.text(
            f"""
            UPDATE department_role_permissions
            SET action_key = 'stage.move:' || substring(
                action_key
                from char_length('stage.move:') + 1
                for char_length(action_key) - char_length('stage.move:->' || :old)
            ) || '->' || :new
            WHERE action_key LIKE 'stage.move:%->' || :old
              AND {CC_DEPT_FILTER}
            """
        ),
        {"old": old, "new": new},
    )


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Rename projects.stage_key on every Content Creation project.
    for old, new in STAGE_RENAMES_FWD:
        bind.execute(
            sa.text(
                """
                UPDATE projects
                SET stage_key = :new
                FROM departments
                WHERE projects.department_id = departments.id
                  AND departments.template_key = 'content_creation'
                  AND projects.stage_key = :old
                """
            ),
            {"old": old, "new": new},
        )

    # 2. Rewrite stage.move action_keys on permission rows in CC departments.
    for old, new in STAGE_RENAMES_FWD:
        _rename_action_keys(bind, old, new)

    # 3. Drop permission rows whose (from,to) is no longer a valid transition.
    valid_keys = [_move_key(f, t) for f, t in NEW_TRANSITIONS]
    bind.execute(
        sa.text(
            f"""
            DELETE FROM department_role_permissions
            WHERE action_key LIKE 'stage.move:%'
              AND action_key NOT IN :valid
              AND {CC_DEPT_FILTER}
            """
        ).bindparams(sa.bindparam("valid", expanding=True)),
        {"valid": valid_keys},
    )

    # 4. Seed brand-new transitions for existing CC department roles. CEO
    #    gets the lot; Assistant-Director + Junior-Director get everything
    #    except publish.
    cc_dept_roles = bind.execute(
        sa.text(
            """
            SELECT r.id AS role_id,
                   r.business_id AS business_id,
                   r.key AS role_key
            FROM department_roles r
            JOIN departments d ON d.id = r.department_id
            WHERE d.template_key = 'content_creation'
            """
        )
    ).mappings().all()

    # Existing action_keys per role — so we don't re-insert duplicates.
    existing = {
        (row.department_role_id, row.action_key)
        for row in bind.execute(
            sa.text(
                """
                SELECT department_role_id, action_key
                FROM department_role_permissions
                WHERE action_key LIKE 'stage.move:%'
                """
            )
        )
    }

    inserts: list[dict[str, object]] = []
    for role in cc_dept_roles:
        role_id = role["role_id"]
        business_id = role["business_id"]
        role_key = role["role_key"]
        if role_key == "ceo":
            targets = NEW_TRANSITIONS
        elif role_key in ("assistant_director", "junior_director"):
            targets = [t for t in NEW_TRANSITIONS if t not in PUBLISH_TRANSITIONS]
        else:
            continue
        for frm, to in targets:
            action_key = _move_key(frm, to)
            if (role_id, action_key) in existing:
                continue
            inserts.append(
                {
                    "department_role_id": str(role_id),
                    "business_id": str(business_id),
                    "action_key": action_key,
                    "allowed": True,
                }
            )

    if inserts:
        bind.execute(
            sa.text(
                """
                INSERT INTO department_role_permissions
                    (id, department_role_id, business_id, action_key, allowed,
                     created_at, updated_at)
                VALUES
                    (gen_random_uuid(), :department_role_id, :business_id,
                     :action_key, :allowed, now(), now())
                """
            ),
            inserts,
        )


# ----- downgrade -----------------------------------------------------------


def downgrade() -> None:
    bind = op.get_bind()

    # 1. Demote any project sitting on shoot_in_progress to shoot_schedule
    #    (lossy — shoots.status preserves the operational fact).
    bind.execute(
        sa.text(
            """
            UPDATE projects
            SET stage_key = 'shoot_schedule'
            FROM departments
            WHERE projects.department_id = departments.id
              AND departments.template_key = 'content_creation'
              AND projects.stage_key = 'shoot_in_progress'
            """
        )
    )

    # 2. Restore the script_locked stage for projects whose lock flag is set
    #    AND that are currently sitting on script_drafting or casting (the
    #    forward migration sends locks to script_drafting; the runtime advances
    #    them to casting).
    bind.execute(
        sa.text(
            """
            UPDATE projects
            SET stage_key = 'script_locked'
            FROM departments
            WHERE projects.department_id = departments.id
              AND departments.template_key = 'content_creation'
              AND projects.script_locked_at IS NOT NULL
              AND projects.stage_key IN ('script_drafting', 'casting')
            """
        )
    )

    # 3. Reverse stage renames in projects.stage_key.
    for old, new in STAGE_RENAMES_BWD:
        bind.execute(
            sa.text(
                """
                UPDATE projects
                SET stage_key = :new
                FROM departments
                WHERE projects.department_id = departments.id
                  AND departments.template_key = 'content_creation'
                  AND projects.stage_key = :old
                """
            ),
            {"old": old, "new": new},
        )

    # 4. Reverse stage renames in permission action_keys (collision-safe).
    for old, new in STAGE_RENAMES_BWD:
        _rename_action_keys(bind, old, new)

    # 5. Drop permission rows that no longer correspond to an old transition.
    old_keys = [_move_key(f, t) for f, t in OLD_TRANSITIONS]
    bind.execute(
        sa.text(
            f"""
            DELETE FROM department_role_permissions
            WHERE action_key LIKE 'stage.move:%'
              AND action_key NOT IN :valid
              AND {CC_DEPT_FILTER}
            """
        ).bindparams(sa.bindparam("valid", expanding=True)),
        {"valid": old_keys},
    )

    # 6. Re-seed any old transitions missing from CC roles (CEO/AD/JD).
    cc_dept_roles = bind.execute(
        sa.text(
            """
            SELECT r.id AS role_id,
                   r.business_id AS business_id,
                   r.key AS role_key
            FROM department_roles r
            JOIN departments d ON d.id = r.department_id
            WHERE d.template_key = 'content_creation'
            """
        )
    ).mappings().all()
    existing = {
        (row.department_role_id, row.action_key)
        for row in bind.execute(
            sa.text(
                """
                SELECT department_role_id, action_key
                FROM department_role_permissions
                WHERE action_key LIKE 'stage.move:%'
                """
            )
        )
    }
    inserts: list[dict[str, object]] = []
    for role in cc_dept_roles:
        role_id = role["role_id"]
        business_id = role["business_id"]
        role_key = role["role_key"]
        if role_key == "ceo":
            targets = OLD_TRANSITIONS
        elif role_key in ("assistant_director", "junior_director"):
            targets = [t for t in OLD_TRANSITIONS if t not in OLD_PUBLISH]
        else:
            continue
        for frm, to in targets:
            action_key = _move_key(frm, to)
            if (role_id, action_key) in existing:
                continue
            inserts.append(
                {
                    "department_role_id": str(role_id),
                    "business_id": str(business_id),
                    "action_key": action_key,
                    "allowed": True,
                }
            )
    if inserts:
        bind.execute(
            sa.text(
                """
                INSERT INTO department_role_permissions
                    (id, department_role_id, business_id, action_key, allowed,
                     created_at, updated_at)
                VALUES
                    (gen_random_uuid(), :department_role_id, :business_id,
                     :action_key, :allowed, now(), now())
                """
            ),
            inserts,
        )
