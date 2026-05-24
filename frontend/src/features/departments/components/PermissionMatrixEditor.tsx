"use client";

import { Plus } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { listPermissions, upsertPermission } from "@/features/departments/api";
import type { DepartmentRole, Permission } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

/**
 * Permission matrix for one role. Action keys are typed in directly for
 * Phase A — the registry-driven picker ships in Phase D.
 */
export function PermissionMatrixEditor({ role }: { role: DepartmentRole }) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
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

  async function flip(p: Permission, next: boolean) {
    try {
      const updated = await upsertPermission(role.id, {
        action_key: p.action_key,
        allowed: next,
      });
      setRows((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r)),
      );
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
        return [...without, created].sort((a, b) =>
          a.action_key.localeCompare(b.action_key),
        );
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
      <CardContent className="space-y-4">
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("action_key")}</TableHead>
                <TableHead className="w-24 text-right">{t("allowed")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={2} className="text-muted-foreground">
                    {t("permissions_empty")}
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-mono text-xs">
                      {p.action_key}
                    </TableCell>
                    <TableCell className="text-right">
                      <Switch
                        checked={p.allowed}
                        onCheckedChange={(v) => void flip(p, v)}
                      />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}

        <form className="flex gap-2" onSubmit={addAction}>
          <Input
            value={newAction}
            onChange={(e) => setNewAction(e.target.value)}
            placeholder="script_versioning.lock"
            className="flex-1"
          />
          <Button type="submit" size="sm">
            <Plus className="mr-1 size-4" />
            {t("add_action")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
