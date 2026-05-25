"""phaseB: migrate the real-estate flow into a Content Creation department

Creates the "Sons Real Estate" business, instantiates the Content Creation
department template inside it, then backfills every legacy project + child
row with `business_id` (and `department_id` / `stage_id` on `projects`).

Idempotent: every insert/upsert checks for the existing row first, so this
can be safely re-run against a partially-migrated DB.

Phase-B note: the legacy `projects.stage` enum column stays — the follow-up
migration in B4 flips `business_id`/`department_id`/`stage_id` to NOT NULL
and drops the legacy `stage` column. We keep the mirror until both backend
and frontend code have moved to reading from `stage_id`.

Revision ID: f1c7a4e9b2d6
Revises: e8f3c1a2b9d4
Create Date: 2026-05-25
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Sequence, Union

from alembic import op
from sqlalchemy import text

from app.config import get_settings
from app.seeds.templates import all_templates, get_template

revision: str = "f1c7a4e9b2d6"
down_revision: Union[str, Sequence[str], None] = "e8f3c1a2b9d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SONS_REAL_ESTATE_SLUG = "sons-real-estate"
SONS_REAL_ESTATE_NAME = "Sons Real Estate"
CONTENT_CREATION_KEY = "content_creation"
CONTENT_CREATION_DEPT_SLUG = "content-creation"

# Child tables that need a business_id backfill. `business_id` lives directly
# on each row; the JOIN path tells us where to look up the value.
#
#   (table, extra_from_tables, where_clause)
#
# `projects p` is added implicitly to the UPDATE's FROM clause; multi-hop
# children must list their intermediate tables in `extra_from_tables` (a
# comma-separated string) because Postgres requires every table referenced
# in the WHERE clause to appear in either the target or the FROM list.
CHILD_BACKFILL_PLAN: list[tuple[str, str, str]] = [
    # 1-hop tables: row.project_id -> projects.business_id
    ("scripts", "", "scripts.project_id = p.id"),
    ("edit_versions", "", "edit_versions.project_id = p.id"),
    ("locations", "", "locations.project_id = p.id"),
    ("cast_members", "", "cast_members.project_id = p.id"),
    ("shoots", "", "shoots.project_id = p.id"),
    ("activities", "", "activities.project_id = p.id"),
    ("notifications", "", "notifications.project_id = p.id"),
    # 2-hop: through scripts
    (
        "script_versions",
        "scripts",
        "script_versions.script_id = scripts.id AND scripts.project_id = p.id",
    ),
    # 3-hop: through script_versions → scripts
    (
        "script_comments",
        "script_versions, scripts",
        "script_comments.version_id = script_versions.id "
        "AND script_versions.script_id = scripts.id "
        "AND scripts.project_id = p.id",
    ),
    # 2-hop: through edit_versions
    (
        "edit_comments",
        "edit_versions",
        "edit_comments.edit_version_id = edit_versions.id "
        "AND edit_versions.project_id = p.id",
    ),
    # 2-hop: through locations
    (
        "location_photos",
        "locations",
        "location_photos.location_id = locations.id AND locations.project_id = p.id",
    ),
]


def _upsert_department_templates(bind: Any) -> None:
    """Materialise every registered template into `department_templates`.

    Identical to `scripts/seed_templates.py` but inlined as a sync ORM-free
    upsert so the migration doesn't depend on the async session machinery.
    """
    for tpl in all_templates():
        bind.execute(
            text(
                """
                INSERT INTO department_templates (
                    id, key, name, description,
                    default_capabilities, default_stages, default_roles,
                    is_system
                )
                VALUES (
                    gen_random_uuid(), :key, :name, :description,
                    CAST(:default_capabilities AS JSONB),
                    CAST(:default_stages AS JSONB),
                    CAST(:default_roles AS JSONB),
                    :is_system
                )
                ON CONFLICT (key) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    default_capabilities = EXCLUDED.default_capabilities,
                    default_stages = EXCLUDED.default_stages,
                    default_roles = EXCLUDED.default_roles,
                    is_system = EXCLUDED.is_system,
                    updated_at = now()
                """
            ),
            {
                "key": tpl["key"],
                "name": tpl["name"],
                "description": tpl.get("description"),
                "default_capabilities": json.dumps(tpl.get("default_capabilities", [])),
                "default_stages": json.dumps(tpl.get("default_stages", [])),
                "default_roles": json.dumps(tpl.get("default_roles", [])),
                "is_system": bool(tpl.get("is_system", False)),
            },
        )


def _find_ceo(bind: Any) -> uuid.UUID | None:
    settings = get_settings()
    row = bind.execute(
        text(
            "SELECT id FROM users "
            "WHERE lower(email) = lower(:email) AND deleted_at IS NULL "
            "LIMIT 1"
        ),
        {"email": settings.ceo_email},
    ).first()
    if row is None:
        # Fall back to any user with the CEO role; in dev some DBs were
        # seeded before CEO_EMAIL was canonical.
        row = bind.execute(
            text("SELECT id FROM users WHERE role = 'ceo' AND deleted_at IS NULL LIMIT 1")
        ).first()
    return row[0] if row else None


def _upsert_business(bind: Any, ceo_id: uuid.UUID) -> uuid.UUID | None:
    """Create or return the existing 'Sons Real Estate' business id."""
    existing = bind.execute(
        text("SELECT id FROM businesses WHERE slug = :slug AND deleted_at IS NULL"),
        {"slug": SONS_REAL_ESTATE_SLUG},
    ).first()
    if existing is not None:
        return existing[0]

    new_id = uuid.uuid4()
    bind.execute(
        text(
            "INSERT INTO businesses (id, name, slug, owner_user_id) "
            "VALUES (:id, :name, :slug, :owner)"
        ),
        {
            "id": new_id,
            "name": SONS_REAL_ESTATE_NAME,
            "slug": SONS_REAL_ESTATE_SLUG,
            "owner": ceo_id,
        },
    )
    return new_id


def _ensure_business_memberships(bind: Any, business_id: uuid.UUID) -> None:
    """Every existing non-deleted user becomes an active member."""
    bind.execute(
        text(
            """
            INSERT INTO business_memberships (
                id, business_id, user_id, status, joined_at
            )
            SELECT
                gen_random_uuid(),
                :business_id,
                u.id,
                'active'::business_membership_status,
                now()
            FROM users u
            WHERE u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM business_memberships m
                  WHERE m.business_id = :business_id AND m.user_id = u.id
              )
            """
        ),
        {"business_id": business_id},
    )


def _existing_department(bind: Any, business_id: uuid.UUID) -> uuid.UUID | None:
    row = bind.execute(
        text(
            "SELECT id FROM departments "
            "WHERE business_id = :bid AND slug = :slug"
        ),
        {"bid": business_id, "slug": CONTENT_CREATION_DEPT_SLUG},
    ).first()
    return row[0] if row else None


def _instantiate_content_creation_department(
    bind: Any, business_id: uuid.UUID
) -> uuid.UUID:
    """Create the department + stages + roles + permissions if not already there.

    Synchronous mirror of `app.services.department_service.create_department`
    so we don't pull async machinery into the migration runtime.
    """
    existing = _existing_department(bind, business_id)
    if existing is not None:
        return existing

    template = get_template(CONTENT_CREATION_KEY)
    dept_id = uuid.uuid4()
    bind.execute(
        text(
            """
            INSERT INTO departments (
                id, business_id, template_key, name, slug, capabilities
            )
            VALUES (
                :id, :bid, :tk, :name, :slug, CAST(:capabilities AS JSONB)
            )
            """
        ),
        {
            "id": dept_id,
            "bid": business_id,
            "tk": template["key"],
            "name": template["name"],
            "slug": CONTENT_CREATION_DEPT_SLUG,
            "capabilities": json.dumps(template.get("default_capabilities", [])),
        },
    )

    # --- Stages: two passes (create rows, then resolve allowed-from keys → ids).
    stage_id_by_key: dict[str, uuid.UUID] = {}
    for idx, raw in enumerate(template.get("default_stages", [])):
        stage_id = uuid.uuid4()
        stage_id_by_key[raw["key"]] = stage_id
        bind.execute(
            text(
                """
                INSERT INTO department_stages (
                    id, department_id, business_id, key, name_i18n,
                    order_index, is_terminal, color, allowed_from_stage_ids
                )
                VALUES (
                    :id, :dept, :bid, :key, CAST(:name_i18n AS JSONB),
                    :order_index, :is_terminal, :color, CAST('[]' AS JSONB)
                )
                """
            ),
            {
                "id": stage_id,
                "dept": dept_id,
                "bid": business_id,
                "key": raw["key"],
                "name_i18n": json.dumps(raw.get("name_i18n", {})),
                "order_index": raw.get("order_index", idx),
                "is_terminal": bool(raw.get("is_terminal", False)),
                "color": raw.get("color"),
            },
        )

    for raw in template.get("default_stages", []):
        pending_keys: list[str] = raw.get("allowed_from_stage_keys", []) or []
        if not pending_keys:
            continue
        resolved = [str(stage_id_by_key[k]) for k in pending_keys if k in stage_id_by_key]
        bind.execute(
            text(
                "UPDATE department_stages SET allowed_from_stage_ids = CAST(:ids AS JSONB) "
                "WHERE department_id = :dept AND key = :key"
            ),
            {
                "ids": json.dumps(resolved),
                "dept": dept_id,
                "key": raw["key"],
            },
        )

    # --- Roles
    role_id_by_key: dict[str, uuid.UUID] = {}
    for raw in template.get("default_roles", []):
        role_id = uuid.uuid4()
        role_id_by_key[raw["key"]] = role_id
        bind.execute(
            text(
                """
                INSERT INTO department_roles (
                    id, department_id, business_id, key, name_i18n, description
                )
                VALUES (
                    :id, :dept, :bid, :key, CAST(:name_i18n AS JSONB), :description
                )
                """
            ),
            {
                "id": role_id,
                "dept": dept_id,
                "bid": business_id,
                "key": raw["key"],
                "name_i18n": json.dumps(raw.get("name_i18n", {})),
                "description": raw.get("description"),
            },
        )

    # --- Role permissions
    for raw in template.get("default_role_permissions", []):
        role_key = raw.get("role_key")
        action_key = raw.get("action_key")
        if not role_key or not action_key:
            continue
        role_id = role_id_by_key.get(role_key)
        if role_id is None:
            continue
        bind.execute(
            text(
                """
                INSERT INTO department_role_permissions (
                    id, department_role_id, business_id, action_key, allowed
                )
                VALUES (gen_random_uuid(), :role_id, :bid, :action, :allowed)
                ON CONFLICT (department_role_id, action_key) DO UPDATE SET
                    allowed = EXCLUDED.allowed,
                    updated_at = now()
                """
            ),
            {
                "role_id": role_id,
                "bid": business_id,
                "action": action_key,
                "allowed": bool(raw.get("allowed", False)),
            },
        )

    return dept_id


def _assign_department_members(
    bind: Any, business_id: uuid.UUID, department_id: uuid.UUID
) -> None:
    """Map each user's global `Role` to the matching department role.

    Role keys in the Content Creation template intentionally match the
    `Role` enum values 1:1, so the mapping is a direct lookup.
    """
    bind.execute(
        text(
            """
            INSERT INTO department_memberships (
                id, department_id, business_id, user_id, role_id
            )
            SELECT
                gen_random_uuid(),
                :dept,
                :bid,
                u.id,
                r.id
            FROM users u
            JOIN department_roles r
              ON r.department_id = :dept AND r.key::text = u.role::text
            WHERE u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM department_memberships m
                  WHERE m.department_id = :dept AND m.user_id = u.id
              )
            """
        ),
        {"dept": department_id, "bid": business_id},
    )


def _backfill_projects(
    bind: Any, business_id: uuid.UUID, department_id: uuid.UUID
) -> None:
    """Set `business_id`/`department_id`/`stage_id` on every existing project.

    `stage_id` is resolved by matching the legacy enum `stage` to the same
    `key` in `department_stages` for this department.
    """
    bind.execute(
        text(
            """
            UPDATE projects p
               SET business_id = :bid,
                   department_id = :dept,
                   stage_id = ds.id
              FROM department_stages ds
             WHERE ds.department_id = :dept
               AND ds.key = p.stage::text
               AND (
                   p.business_id IS NULL
                OR p.department_id IS NULL
                OR p.stage_id IS NULL
               )
            """
        ),
        {"bid": business_id, "dept": department_id},
    )


def _backfill_child_business_id(bind: Any) -> None:
    """Populate `business_id` on every child row via its parent project.

    Each statement is `UPDATE … FROM projects p[, intermediate_tables] WHERE …`
    so the join walks from the row back to its `projects.business_id`. After
    Phase B's project backfill above, every project has a `business_id`, so
    this walks the whole graph in one pass per table.
    """
    for table, extra_from, where_expr in CHILD_BACKFILL_PLAN:
        from_clause = f"projects p, {extra_from}" if extra_from else "projects p"
        bind.execute(
            text(
                f"""
                UPDATE {table}
                   SET business_id = p.business_id
                  FROM {from_clause}
                 WHERE {where_expr}
                   AND {table}.business_id IS NULL
                   AND p.business_id IS NOT NULL
                """
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    _upsert_department_templates(bind)

    ceo_id = _find_ceo(bind)
    if ceo_id is None:
        # Fresh DB with no users yet — nothing to migrate. Templates are in
        # place so the eventual seed flow + future business creation works.
        return

    business_id = _upsert_business(bind, ceo_id)
    if business_id is None:
        return

    _ensure_business_memberships(bind, business_id)
    department_id = _instantiate_content_creation_department(bind, business_id)
    _assign_department_members(bind, business_id, department_id)
    _backfill_projects(bind, business_id, department_id)
    _backfill_child_business_id(bind)


def downgrade() -> None:
    """Undo only what's directly attributable to this migration.

    Drops the Sons Real Estate business + its Content Creation department +
    every membership row + every child-table business_id link. The legacy
    `projects.stage` enum column is untouched (it's the original column from
    Phase 1 and remains the fallback while Phase B's code refactors land).
    """
    bind = op.get_bind()

    # Clear the FKs on projects so the department can be dropped.
    bind.execute(
        text(
            """
            UPDATE projects
               SET business_id = NULL,
                   department_id = NULL,
                   stage_id = NULL
             WHERE business_id IN (
                 SELECT id FROM businesses WHERE slug = :slug
             )
            """
        ),
        {"slug": SONS_REAL_ESTATE_SLUG},
    )

    # Null out the denormalised business_id on child tables that point at
    # this business — keeps the downgrade explicit even though the cleanup
    # below would cascade.
    for table, _extra_from, _where_expr in CHILD_BACKFILL_PLAN:
        bind.execute(
            text(
                f"""
                UPDATE {table}
                   SET business_id = NULL
                  WHERE business_id IN (
                      SELECT id FROM businesses WHERE slug = :slug
                  )
                """
            ),
            {"slug": SONS_REAL_ESTATE_SLUG},
        )

    bind.execute(
        text("DELETE FROM businesses WHERE slug = :slug"),
        {"slug": SONS_REAL_ESTATE_SLUG},
    )
    # Departments + memberships + stages + roles + permissions cascade-delete
    # via the FK ondelete=CASCADE on businesses.

    # Pull the seeded templates back out — they're a no-op if nothing
    # references them.
    bind.execute(
        text("DELETE FROM department_templates WHERE key = :key"),
        {"key": CONTENT_CREATION_KEY},
    )
