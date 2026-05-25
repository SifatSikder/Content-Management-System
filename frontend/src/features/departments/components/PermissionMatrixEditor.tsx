"use client";

import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useDepartmentStages } from "@/features/departments/hooks/useDepartmentStages";
import { useStageLabel } from "@/features/departments/hooks/useStageLabel";
import { listPermissions, upsertPermission } from "@/features/departments/api";
import type { Department, DepartmentRole, Permission } from "@/features/departments/types";
import {
  availableActionKeys,
  PERMISSION_GROUP_ORDER,
  type PermissionDisplay,
  permissionDisplay,
} from "@/features/departments/lib/permissionLabel";
import { ApiError } from "@/lib/api-client";

/**
 * Permission matrix for one role.
 *
 * Every action available in this department renders as a toggleable row,
 * not just the ones already persisted. The available set comes from
 * `availableActionKeys(capabilities, stages)` — project actions + the
 * action keys declared by each enabled capability + every stage transition
 * the workflow allows. Rows that don't yet have a `(role, action)` row in
 * the DB show as off and only get a row when toggled on. Persisted rows
 * whose key isn't in the available set (e.g. a backend action the
 * frontend registry hasn't shipped yet) still render — the matrix is
 * additive, never silently hides a stored permission.
 *
 * Renders as a section (no outer `Card`) so callers can compose it inline
 * inside another card — the role list above it, specifically.
 */
export function PermissionMatrixEditor({
  role,
  department,
}: {
  role: DepartmentRole;
  department: Department;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const resolveStage = useStageLabel(role.department_id);
  const { stages } = useDepartmentStages(role.department_id);
  const [rows, setRows] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());

  function toggleGroup(groupKey: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) next.delete(groupKey);
      else next.add(groupKey);
      return next;
    });
  }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listPermissions(role.id);
      setRows(res.items);
    } catch (exc) {
      toast.error(exc instanceof Error ? exc.message : tCommon("error"));
    } finally {
      setLoading(false);
    }
  }, [role.id, tCommon]);

  useEffect(() => {
    void load();
  }, [load]);

  // Merge available actions with persisted rows so every known action gets
  // a row, even if no `(role, action)` record exists yet. Persisted rows
  // with unknown keys land at the end (defensive: never hide a stored
  // permission). Then bucket by display group.
  const groups = useMemo(() => {
    const persisted = new Map(rows.map((r) => [r.action_key, r] as const));
    const seen = new Set<string>();
    const merged: { key: string; perm: Permission | null }[] = [];

    for (const key of availableActionKeys(department.capabilities, stages)) {
      if (seen.has(key)) continue;
      seen.add(key);
      merged.push({ key, perm: persisted.get(key) ?? null });
    }
    for (const r of rows) {
      if (seen.has(r.action_key)) continue;
      seen.add(r.action_key);
      merged.push({ key: r.action_key, perm: r });
    }

    const buckets = new Map<
      string,
      {
        label: string;
        items: { key: string; perm: Permission | null; display: PermissionDisplay }[];
      }
    >();
    for (const entry of merged) {
      const display = permissionDisplay(entry.key, resolveStage);
      const bucket = buckets.get(display.group);
      if (bucket) {
        bucket.items.push({ ...entry, display });
      } else {
        buckets.set(display.group, {
          label: display.groupLabel,
          items: [{ ...entry, display }],
        });
      }
    }
    for (const bucket of buckets.values()) {
      bucket.items.sort((a, b) => a.display.title.localeCompare(b.display.title));
    }
    return PERMISSION_GROUP_ORDER.flatMap((key) => {
      const bucket = buckets.get(key);
      return bucket ? [{ key, ...bucket }] : [];
    });
  }, [rows, resolveStage, department.capabilities, stages]);

  async function toggle(actionKey: string, next: boolean) {
    setPendingKey(actionKey);
    try {
      const updated = await upsertPermission(role.id, {
        action_key: actionKey,
        allowed: next,
      });
      setRows((prev) => {
        const without = prev.filter((r) => r.action_key !== actionKey);
        return [...without, updated];
      });
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    } finally {
      setPendingKey(null);
    }
  }

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h3 className="text-sm font-semibold">
          {t("permissions_title")} — {role.name_i18n.en ?? role.key}
        </h3>
        <p className="text-muted-foreground text-xs">{t("permissions_subtitle")}</p>
      </header>

      {loading ? (
        <Skeleton className="h-24 w-full" />
      ) : groups.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("permissions_empty")}</p>
      ) : (
        <div className="space-y-5">
          {groups.map((group) => {
            const isCollapsed = collapsed.has(group.key);
            const headerId = `perm-group-${role.id}-${group.key}`;
            return (
              <section key={group.key} className="space-y-2">
                <button
                  type="button"
                  id={headerId}
                  onClick={() => toggleGroup(group.key)}
                  aria-expanded={!isCollapsed}
                  aria-controls={`${headerId}-list`}
                  className="text-muted-foreground hover:text-foreground flex w-full items-center gap-1.5 text-xs font-medium tracking-wide uppercase"
                >
                  <ChevronDown
                    className={cn(
                      "size-3.5 transition-transform",
                      isCollapsed ? "-rotate-90" : "rotate-0",
                    )}
                  />
                  <span>{group.label}</span>
                  <span className="text-muted-foreground/70 ml-1 text-[10px] normal-case tracking-normal">
                    ({group.items.length})
                  </span>
                </button>
                {isCollapsed ? null : (
                  <ul
                    id={`${headerId}-list`}
                    className="divide-y rounded-md border"
                  >
                    {group.items.map(({ key, perm, display }) => {
                      const allowed = perm?.allowed ?? false;
                      return (
                        <li
                          key={key}
                          className="flex items-start justify-between gap-4 px-3 py-3"
                        >
                          <div className="min-w-0 flex-1 space-y-0.5">
                            <div className="text-sm font-medium">{display.title}</div>
                            <div className="text-muted-foreground text-xs">
                              {display.description}
                            </div>
                            <div className="text-muted-foreground/70 pt-0.5 font-mono text-[10px]">
                              {key}
                            </div>
                          </div>
                          <Switch
                            checked={allowed}
                            disabled={pendingKey === key}
                            onCheckedChange={(v) => void toggle(key, v)}
                            aria-label={display.title}
                          />
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
    </section>
  );
}
