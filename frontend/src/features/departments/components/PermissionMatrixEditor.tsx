"use client";

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useStageLabel } from "@/features/departments/hooks/useStageLabel";
import { listPermissions, upsertPermission } from "@/features/departments/api";
import type { DepartmentRole, Permission } from "@/features/departments/types";
import {
  PERMISSION_GROUP_ORDER,
  type PermissionDisplay,
  permissionDisplay,
} from "@/features/departments/lib/permissionLabel";
import { ApiError } from "@/lib/api-client";

/**
 * Permission matrix for one role.
 *
 * Rows are grouped (Projects, Stage transitions, per-capability sections)
 * with a human title + description so the CEO toggling roles doesn't have
 * to read raw `script_versioning.lock`-style keys. The wire format is
 * unchanged — toggling a switch still upserts a `(role_id, action_key)`
 * row server-side via `permission_service`.
 */
export function PermissionMatrixEditor({ role }: { role: DepartmentRole }) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const resolveStage = useStageLabel(role.department_id);
  const [rows, setRows] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [newAction, setNewAction] = useState("");

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

  // Bucket rows by display group, preserving a stable inter-row order
  // (alphabetical by title within each group keeps the layout calm as
  // permissions are added/removed).
  const groups = useMemo(() => {
    const buckets = new Map<
      string,
      { label: string; items: { perm: Permission; display: PermissionDisplay }[] }
    >();
    for (const perm of rows) {
      const display = permissionDisplay(perm.action_key, resolveStage);
      const existing = buckets.get(display.group);
      if (existing) {
        existing.items.push({ perm, display });
      } else {
        buckets.set(display.group, {
          label: display.groupLabel,
          items: [{ perm, display }],
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
  }, [rows, resolveStage]);

  async function flip(p: Permission, next: boolean) {
    try {
      const updated = await upsertPermission(role.id, {
        action_key: p.action_key,
        allowed: next,
      });
      setRows((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    }
  }

  async function addAction(e: React.FormEvent) {
    e.preventDefault();
    if (!newAction.trim()) return;
    try {
      const created = await upsertPermission(role.id, {
        action_key: newAction.trim(),
        allowed: true,
      });
      setRows((prev) => {
        const without = prev.filter((r) => r.action_key !== created.action_key);
        return [...without, created];
      });
      setNewAction("");
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {t("permissions_title")} — {role.name_i18n.en ?? role.key}
        </CardTitle>
        <CardDescription>{t("permissions_subtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : rows.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("permissions_empty")}</p>
        ) : (
          <div className="space-y-6">
            {groups.map((group) => (
              <section key={group.key} className="space-y-2">
                <h3 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                  {group.label}
                </h3>
                <ul className="divide-y rounded-md border">
                  {group.items.map(({ perm, display }) => (
                    <li
                      key={perm.id}
                      className="flex items-start justify-between gap-4 px-3 py-3"
                    >
                      <div className="min-w-0 flex-1 space-y-0.5">
                        <div className="text-sm font-medium">{display.title}</div>
                        <div className="text-muted-foreground text-xs">
                          {display.description}
                        </div>
                        <div className="text-muted-foreground/70 pt-0.5 font-mono text-[10px]">
                          {perm.action_key}
                        </div>
                      </div>
                      <Switch
                        checked={perm.allowed}
                        onCheckedChange={(v) => void flip(perm, v)}
                        aria-label={display.title}
                      />
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}

        <details className="text-sm">
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
            {t("add_custom_action_hint")}
          </summary>
          <form className="mt-2 flex gap-2" onSubmit={addAction}>
            <Input
              value={newAction}
              onChange={(e) => setNewAction(e.target.value)}
              placeholder="script_versioning.lock"
              className="flex-1 font-mono text-xs"
            />
            <Button type="submit" size="sm">
              <Plus className="mr-1 size-4" />
              {t("add_action")}
            </Button>
          </form>
        </details>
      </CardContent>
    </Card>
  );
}
