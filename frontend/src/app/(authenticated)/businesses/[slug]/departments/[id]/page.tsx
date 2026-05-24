"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getDepartment } from "@/features/departments/api";
import { DepartmentEditor } from "@/features/departments/components/DepartmentEditor";
import { PermissionMatrixEditor } from "@/features/departments/components/PermissionMatrixEditor";
import { RoleEditor } from "@/features/departments/components/RoleEditor";
import { StageEditor } from "@/features/departments/components/StageEditor";
import type { Department, DepartmentRole } from "@/features/departments/types";

export default function DepartmentDetailPage() {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const params = useParams<{ id: string; slug: string }>();
  const [department, setDepartment] = useState<Department | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedRole, setSelectedRole] = useState<DepartmentRole | null>(null);

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
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{department.name}</h1>
        <p className="text-muted-foreground font-mono text-xs">{department.slug}</p>
      </header>
      <DepartmentEditor department={department} onChanged={setDepartment} />
      <StageEditor departmentId={department.id} />
      <RoleEditor departmentId={department.id} onSelect={setSelectedRole} />
      {selectedRole ? <PermissionMatrixEditor role={selectedRole} /> : null}
    </div>
  );
}
