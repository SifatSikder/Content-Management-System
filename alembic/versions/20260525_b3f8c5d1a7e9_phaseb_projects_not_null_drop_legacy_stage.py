"""phaseB: projects.business_id/department_id/stage_id NOT NULL + drop legacy
`projects.stage` enum column + drop legacy `pipeline_stage` Postgres enum.

Runs immediately after `f1c7a4e9b2d6_phaseb_migrate_real_estate_to_content_creation`
(which backfills the new columns). Any project row that still has a NULL FK
after that backfill blocks the migration — surface it as a clear error rather
than silently turning legacy rows into orphans.

Revision ID: b3f8c5d1a7e9
Revises: f1c7a4e9b2d6
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3f8c5d1a7e9"
down_revision: Union[str, Sequence[str], None] = "f1c7a4e9b2d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Safety check: refuse to proceed if any project is still un-backfilled.
    # Phase B's data migration must have run successfully first.
    row = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM projects "
            "WHERE business_id IS NULL OR department_id IS NULL OR stage_id IS NULL"
        )
    ).first()
    pending = int(row[0]) if row is not None else 0
    if pending > 0:
        raise RuntimeError(
            f"Refusing to NOT-NULL projects.{{business_id, department_id, stage_id}}: "
            f"{pending} project rows still have NULL FKs. Run the Phase B data "
            f"migration first (revision f1c7a4e9b2d6)."
        )

    op.alter_column("projects", "business_id", nullable=False)
    op.alter_column("projects", "department_id", nullable=False)
    op.alter_column("projects", "stage_id", nullable=False)

    # Drop the legacy enum column. The values it carried are mirrored as
    # `department_stages.key` on the Content Creation department's stages,
    # so `project.stage.key` recovers the same string from the relationship.
    op.drop_index("ix_projects_stage", table_name="projects")
    op.drop_column("projects", "stage")

    # The pipeline_stage Postgres enum is no longer referenced anywhere —
    # drop it so we don't carry a dead type forward.
    postgresql.ENUM(name="pipeline_stage").drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()

    # Re-create the pipeline_stage enum.
    pipeline_stage = postgresql.ENUM(
        "idea",
        "script_drafting",
        "script_review",
        "script_locked",
        "location_scouting",
        "casting",
        "shoot_scheduled",
        "shoot_done",
        "editing",
        "final_review",
        "approved_published",
        name="pipeline_stage",
        create_type=True,
    )
    pipeline_stage.create(bind, checkfirst=True)

    op.add_column(
        "projects",
        sa.Column(
            "stage",
            postgresql.ENUM(name="pipeline_stage", create_type=False),
            nullable=True,
        ),
    )
    # Best-effort: restore the legacy `stage` value from the Content Creation
    # department stage's `key` (Phase-B backfill source of truth).
    bind.execute(
        sa.text(
            """
            UPDATE projects p
               SET stage = ds.key::pipeline_stage
              FROM department_stages ds
             WHERE ds.id = p.stage_id
            """
        )
    )
    # Anything left null (project pointed at a stage whose key isn't a valid
    # pipeline_stage member) defaults to 'idea' — we still need the column
    # NOT NULL for the historical schema.
    bind.execute(sa.text("UPDATE projects SET stage = 'idea' WHERE stage IS NULL"))
    op.alter_column("projects", "stage", nullable=False)
    op.create_index("ix_projects_stage", "projects", ["stage"], unique=False)

    op.alter_column("projects", "stage_id", nullable=True)
    op.alter_column("projects", "department_id", nullable=True)
    op.alter_column("projects", "business_id", nullable=True)
