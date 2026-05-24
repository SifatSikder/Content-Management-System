"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

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
import {
  createRole,
  deleteRole,
  listRoles,
} from "@/features/departments/api";
import type { DepartmentRole } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

export function RoleEditor({
  departmentId,
  onSelect,
}: {
  departmentId: string;
  onSelect?: (role: DepartmentRole) => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [roles, setRoles] = useState<DepartmentRole[]>([]);
  const [loading, setLoading] = useState(true);

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
            {roles.map((r) => (
              <div
                key={r.id}
                className="bg-card flex items-center gap-3 rounded-md border px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {r.name_i18n.en ?? r.name_i18n.nl ?? r.key}
                  </div>
                  <div className="text-muted-foreground font-mono text-xs">
                    {r.key}
                  </div>
                </div>
                {onSelect ? (
                  <Button variant="outline" size="sm" onClick={() => onSelect(r)}>
                    {t("edit_permissions")}
                  </Button>
                ) : null}
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete role"
                  onClick={async () => {
                    try {
                      await deleteRole(departmentId, r.id);
                      toast.success(t("role_deleted_toast"));
                      await load();
                    } catch (exc) {
                      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
                      toast.error(msg);
                    }
                  }}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
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
  const [key, setKey] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [nameNl, setNameNl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createRole(departmentId, {
        key: key.trim(),
        name_i18n: { en: nameEn.trim(), nl: nameNl.trim() || nameEn.trim() },
      });
      toast.success(t("role_added_toast"));
      setOpen(false);
      setKey("");
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
            <Label htmlFor="role-key">{t("key_label")}</Label>
            <Input
              id="role-key"
              required
              pattern="^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="member"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role-name-en">{t("name_en_label")}</Label>
            <Input
              id="role-name-en"
              required
              value={nameEn}
              onChange={(e) => setNameEn(e.target.value)}
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
