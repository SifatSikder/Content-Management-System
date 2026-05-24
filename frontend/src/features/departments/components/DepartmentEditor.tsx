"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { updateDepartment } from "@/features/departments/api";
import type { Department } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

/**
 * Rename + capability-list editor for a single department. Capabilities are
 * managed as a comma-separated string in the UI for Phase A — the registry
 * picker UI ships in Phase D.
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
  const [capabilities, setCapabilities] = useState(department.capabilities.join(", "));
  const [saving, setSaving] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const caps = capabilities
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const updated = await updateDepartment(department.id, {
        name: name.trim(),
        capabilities: caps,
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
          <div className="space-y-2">
            <Label htmlFor="dept-caps">{t("capabilities_label")}</Label>
            <Input
              id="dept-caps"
              value={capabilities}
              onChange={(e) => setCapabilities(e.target.value)}
              placeholder="script_versioning, asset_review_with_timecodes"
            />
            <div className="text-muted-foreground flex flex-wrap gap-1 text-xs">
              {department.capabilities.length === 0 ? (
                <span>{t("no_capabilities")}</span>
              ) : (
                department.capabilities.map((c) => (
                  <Badge key={c} variant="secondary">
                    {c}
                  </Badge>
                ))
              )}
            </div>
          </div>
          <Button type="submit" disabled={saving}>
            {saving ? tCommon("loading") : tCommon("save")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
