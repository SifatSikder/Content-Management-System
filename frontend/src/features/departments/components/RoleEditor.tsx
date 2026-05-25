"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { PermissionMatrixEditor } from "@/features/departments/components/PermissionMatrixEditor";
import { useDepartmentStages } from "@/features/departments/hooks/useDepartmentStages";
import { availableActionKeys } from "@/features/departments/lib/permissionLabel";
import {
  createRole,
  deleteRole,
  listPermissions,
  listRoles,
} from "@/features/departments/api";
import type { Department, DepartmentRole } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

/**
 * Roles + permission matrix for a department.
 *
 * Role selection lives inside this component (instead of being lifted into
 * the page) because the permission matrix is a sub-section of the role
 * card now — picking a role expands its matrix in place. Avoids the
 * surprise of "where did the permissions go?" when the selected row is
 * far from the matrix lower on the page.
 */
export function RoleEditor({ department }: { department: Department }) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const departmentId = department.id;
  const { stages } = useDepartmentStages(departmentId);
  const [roles, setRoles] = useState<DepartmentRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [allowedCounts, setAllowedCounts] = useState<Map<string, number>>(
    new Map(),
  );

  // Total actions available in this department — denominator for the
  // "N/M permissions" badge. Recomputes when the template or stage list
  // changes (e.g. a new stage transition broadens the matrix).
  const totalActions = useMemo(
    () => availableActionKeys(department.template_key, stages).length,
    [department.template_key, stages],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listRoles(departmentId);
      setRoles(res.items);
    } catch (exc) {
      toast.error(exc instanceof Error ? exc.message : tCommon("error"));
    } finally {
      setLoading(false);
    }
  }, [departmentId, tCommon]);

  useEffect(() => {
    void load();
  }, [load]);

  // Fetch the allowed-permission count per role. One HTTP per role; with
  // ~5-7 roles per department this is acceptable. `refreshCount(roleId)`
  // is exposed downward so the matrix can re-pull just one role's count
  // after a toggle without refetching all of them.
  const refreshCount = useCallback(async (roleId: string) => {
    try {
      const res = await listPermissions(roleId);
      const allowed = res.items.filter((p) => p.allowed).length;
      setAllowedCounts((prev) => new Map(prev).set(roleId, allowed));
    } catch {
      // Silent — the count badge just stays at its previous value.
    }
  }, []);

  useEffect(() => {
    if (roles.length === 0) return;
    let cancelled = false;
    Promise.all(
      roles.map(async (r) => {
        try {
          const res = await listPermissions(r.id);
          return [r.id, res.items.filter((p) => p.allowed).length] as const;
        } catch {
          return [r.id, 0] as const;
        }
      }),
    ).then((entries) => {
      if (cancelled) return;
      setAllowedCounts(new Map(entries));
    });
    return () => {
      cancelled = true;
    };
  }, [roles]);

  const selectedRole = roles.find((r) => r.id === selectedRoleId) ?? null;

  function togglePermissions(role: DepartmentRole) {
    setSelectedRoleId((prev) => (prev === role.id ? null : role.id));
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{t("roles_title")}</CardTitle>
            <CardDescription>{t("roles_subtitle")}</CardDescription>
          </div>
          <AddRoleDialog departmentId={departmentId} onCreated={() => void load()} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : roles.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("roles_empty")}</p>
        ) : (
          <div className="space-y-2">
            {roles.map((r) => {
              const isSelected = r.id === selectedRoleId;
              return (
                <div
                  key={r.id}
                  className={cn(
                    "rounded-md border transition-colors",
                    isSelected ? "border-ring bg-accent/30" : "bg-card",
                  )}
                >
                  <div className="flex items-center gap-3 px-3 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {r.name_i18n.en ?? r.name_i18n.nl ?? r.key}
                      </div>
                      <div className="text-muted-foreground font-mono text-xs">
                        {r.key}
                      </div>
                    </div>
                    <Badge variant="outline" className="font-normal">
                      {t("permissions_count", {
                        allowed: allowedCounts.get(r.id) ?? 0,
                        total: totalActions,
                      })}
                    </Badge>
                    <Button
                      variant={isSelected ? "secondary" : "outline"}
                      size="sm"
                      onClick={() => togglePermissions(r)}
                    >
                      {isSelected
                        ? t("hide_permissions")
                        : t("edit_permissions")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete role"
                      onClick={async () => {
                        try {
                          await deleteRole(departmentId, r.id);
                          toast.success(t("role_deleted_toast"));
                          if (selectedRoleId === r.id) setSelectedRoleId(null);
                          await load();
                        } catch (exc) {
                          const msg =
                            exc instanceof ApiError ? exc.message : tCommon("error");
                          toast.error(msg);
                        }
                      }}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                  {isSelected && selectedRole ? (
                    <div className="border-t px-3 py-4">
                      <PermissionMatrixEditor
                        role={selectedRole}
                        department={department}
                        onPermissionChanged={() => void refreshCount(selectedRole.id)}
                      />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Slugify a free-form role name into a stable backend key. The backend
 * regex (`app/schemas/department.py::CreateRoleBody`) is
 * `^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$` — lowercase alphanumeric with
 * single-character underscore separators, no leading/trailing underscore.
 */
function slugifyRoleKey(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function AddRoleDialog({
  departmentId,
  onCreated,
}: {
  departmentId: string;
  onCreated: () => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [nameEn, setNameEn] = useState("");
  const [nameNl, setNameNl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const en = nameEn.trim();
    const nl = nameNl.trim() || en;
    const key = slugifyRoleKey(en);
    if (!key) {
      toast.error(tCommon("error"));
      return;
    }
    setSubmitting(true);
    try {
      await createRole(departmentId, {
        key,
        name_i18n: { en, nl },
      });
      toast.success(t("role_added_toast"));
      setOpen(false);
      setNameEn("");
      setNameNl("");
      onCreated();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 size-4" />
          {t("add_role")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("add_role")}</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2">
            <Label htmlFor="role-name-en">{t("name_en_label")}</Label>
            <Input
              id="role-name-en"
              required
              value={nameEn}
              onChange={(e) => setNameEn(e.target.value)}
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role-name-nl">{t("name_nl_label")}</Label>
            <Input
              id="role-name-nl"
              value={nameNl}
              onChange={(e) => setNameNl(e.target.value)}
              placeholder={nameEn}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? tCommon("loading") : t("add_role")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
