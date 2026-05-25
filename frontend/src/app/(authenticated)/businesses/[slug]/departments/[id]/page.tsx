"use client";

import { Loader2, Pencil } from "lucide-react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getDepartment, updateDepartment } from "@/features/departments/api";
import { DepartmentMembersEditor } from "@/features/departments/components/DepartmentMembersEditor";
import { RoleEditor } from "@/features/departments/components/RoleEditor";
import { StageEditor } from "@/features/departments/components/StageEditor";
import type { Department } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

export default function DepartmentDetailPage() {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const params = useParams<{ id: string; slug: string }>();
  const [department, setDepartment] = useState<Department | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingName, setEditingName] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [savingName, setSavingName] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await getDepartment(params.id);
      setDepartment(d);
    } catch (exc) {
      toast.error(exc instanceof Error ? exc.message : tCommon("error"));
    } finally {
      setLoading(false);
    }
  }, [params.id, tCommon]);

  useEffect(() => {
    void load();
  }, [load]);

  function startEdit() {
    if (!department) return;
    setDraftName(department.name);
    setEditingName(true);
  }

  function cancelEdit() {
    setEditingName(false);
    setDraftName("");
  }

  async function commitEdit() {
    if (!department) return;
    const trimmed = draftName.trim();
    // No-op if blank or unchanged — exit edit mode without a round-trip.
    if (!trimmed || trimmed === department.name) {
      cancelEdit();
      return;
    }
    setSavingName(true);
    try {
      const updated = await updateDepartment(department.id, { name: trimmed });
      setDepartment(updated);
      toast.success(t("saved_toast"));
      setEditingName(false);
    } catch (exc) {
      toast.error(exc instanceof ApiError ? exc.message : tCommon("error"));
      // Leave the editor open so the user can fix + retry.
    } finally {
      setSavingName(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4 p-6">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!department) {
    return (
      <div className="mx-auto w-full max-w-5xl p-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("not_found")}</CardTitle>
          </CardHeader>
          <CardContent>{t("not_found_body")}</CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          {editingName ? (
            <>
              <Input
                autoFocus
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                onBlur={() => void commitEdit()}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void commitEdit();
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    cancelEdit();
                  }
                }}
                disabled={savingName}
                aria-label={t("name_label")}
                className="h-10 max-w-md text-2xl font-semibold tracking-tight"
              />
              {savingName ? (
                <Loader2 className="text-muted-foreground size-4 animate-spin" />
              ) : null}
            </>
          ) : (
            <>
              <h1 className="text-2xl font-semibold tracking-tight">
                {department.name}
              </h1>
              <Button
                variant="ghost"
                size="icon"
                onClick={startEdit}
                aria-label={t("rename")}
                className="text-muted-foreground hover:text-foreground"
              >
                <Pencil className="size-4" />
              </Button>
            </>
          )}
        </div>
        <p className="text-muted-foreground font-mono text-xs">{department.slug}</p>
      </header>

      {/*
        Roles + Members live together — you usually define a role and then
        invite members into it. Roles is the default tab because the flow
        starts there. Stages live below — the kanban workflow is its own
        concern, set up independently of who has access.
      */}
      <Card>
        <CardContent>
          <Tabs defaultValue="roles" className="flex-col">
            <TabsList className="w-full">
              <TabsTrigger value="roles">{t("roles_title")}</TabsTrigger>
              <TabsTrigger value="members">{t("members_title")}</TabsTrigger>
            </TabsList>
            <TabsContent value="roles" className="mt-4">
              <RoleEditor department={department} />
            </TabsContent>
            <TabsContent value="members" className="mt-4">
              <DepartmentMembersEditor departmentId={department.id} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      <StageEditor departmentId={department.id} />
    </div>
  );
}
