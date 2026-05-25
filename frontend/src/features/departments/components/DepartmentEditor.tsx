"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
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
import { Label } from "@/components/ui/label";
import { updateDepartment } from "@/features/departments/api";
import type { Department } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

/**
 * Rename a single department.
 *
 * Feature set is fixed by `template_key` (see
 * `frontend/src/features/projects/lib/projectTabs.ts`) — no per-department
 * capability toggle. Stage, role, and member editors live elsewhere on
 * the page.
 */
export function DepartmentEditor({
  department,
  onChanged,
}: {
  department: Department;
  onChanged: (d: Department) => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [name, setName] = useState(department.name);
  const [saving, setSaving] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateDepartment(department.id, {
        name: name.trim(),
      });
      toast.success(t("saved_toast"));
      onChanged(updated);
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("editor_title")}</CardTitle>
        <CardDescription>{t("editor_subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={save}>
          <div className="space-y-2">
            <Label htmlFor="dept-name">{t("name_label")}</Label>
            <Input
              id="dept-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={saving}>
            {saving ? tCommon("loading") : tCommon("save")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
