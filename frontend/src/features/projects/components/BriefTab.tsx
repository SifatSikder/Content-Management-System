"use client";

import { Pencil } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { updateProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import { CATEGORIES, canEditProject, type Category, type Role } from "@/lib/enums";

interface Props {
  project: Project;
  role: Role;
  isOwner: boolean;
  onUpdated: (p: Project) => void;
}

export function BriefTab({ project, role, isOwner, onUpdated }: Props) {
  const t = useTranslations("projects");
  const tCat = useTranslations("categories");
  const tCommon = useTranslations("common");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");

  const editable = canEditProject(role, isOwner) && !project.deleted_at;
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(project.title);
  const [description, setDescription] = useState(project.description ?? "");
  const [category, setCategory] = useState<Category>(project.category);
  const [dueDate, setDueDate] = useState(project.due_date ?? "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const updated = await updateProject(project.id, {
        title,
        description: description || null,
        category,
        due_date: dueDate || null,
      });
      onUpdated(updated);
      toast.success(tToast("project_updated"));
      setEditing(false);
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{t("title_label")}</CardTitle>
        {editable && !editing && (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="mr-2 size-4" />
            {tCommon("edit")}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {!editing ? (
          <>
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">{t("title_label")}</Label>
              <p className="text-sm">{project.title}</p>
            </div>
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">{t("category_label")}</Label>
              <Badge variant="secondary" className="w-fit">
                {tCat(project.category)}
              </Badge>
            </div>
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">{t("description_label")}</Label>
              <p className="text-sm whitespace-pre-wrap">
                {project.description ?? tCommon("none")}
              </p>
            </div>
            <div className="space-y-1">
              <Label className="text-muted-foreground text-xs">{t("due_date_label")}</Label>
              <p className="text-sm">{project.due_date ?? tCommon("no_date")}</p>
            </div>
          </>
        ) : (
          <>
            <div className="space-y-1">
              <Label className="text-xs">{t("title_label")}</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">{t("category_label")}</Label>
              <Select value={category} onValueChange={(v) => setCategory(v as Category)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {tCat(c)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">{t("description_label")}</Label>
              <Textarea
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">{t("due_date_label")}</Label>
              <Input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={save} disabled={saving}>
                {tCommon("save")}
              </Button>
              <Button variant="outline" onClick={() => setEditing(false)} disabled={saving}>
                {tCommon("cancel")}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
