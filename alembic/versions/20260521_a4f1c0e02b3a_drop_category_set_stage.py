"""drop category_set pipeline stage

Postgres can't DROP VALUE from an enum directly, so we recreate the type
without category_set and swap the projects.stage column over to it. Safe
to run against an empty projects table (we wiped before this migration);
if non-empty, any rows in category_set would have to be relocated first.

Revision ID: a4f1c0e02b3a
Revises: 882961d153d9
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a4f1c0e02b3a"
down_revision: Union[str, Sequence[str], None] = "882961d153d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_STAGES = (
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
)

OLD_STAGES = (
    "idea",
    "category_set",
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
)


def _swap(target_values: Sequence[str], stage_value_for_legacy: str) -> None:
    """Rebuild pipeline_stage with `target_values`.

    Any rows whose current value is no longer in `target_values` are folded
    into `stage_value_for_legacy` (cast via text) so the USING clause never
    fails. Only meaningful for the upgrade (category_set → idea); the
    downgrade has no orphans.
    """
    values_sql = ", ".join(f"'{v}'" for v in target_values)
    legacy_set = set(OLD_STAGES) - set(target_values) if set(target_values) < set(OLD_STAGES) else set()

    op.execute(f"CREATE TYPE pipeline_stage_new AS ENUM ({values_sql})")
    if legacy_set:
        legacy_in = ", ".join(f"'{v}'" for v in legacy_set)
        op.execute(
            "UPDATE projects SET stage = "
            f"'{stage_value_for_legacy}'::pipeline_stage WHERE stage::text IN ({legacy_in})"
        )
    op.execute(
        "ALTER TABLE projects ALTER COLUMN stage TYPE pipeline_stage_new "
        "USING stage::text::pipeline_stage_new"
    )
    op.execute("DROP TYPE pipeline_stage")
    op.execute("ALTER TYPE pipeline_stage_new RENAME TO pipeline_stage")


def upgrade() -> None:
    _swap(NEW_STAGES, stage_value_for_legacy="idea")


def downgrade() -> None:
    # Re-introducing category_set leaves no rows in it — that's fine.
    _swap(OLD_STAGES, stage_value_for_legacy="idea")
