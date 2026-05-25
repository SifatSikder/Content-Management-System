"use client";

import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useDepartmentStages } from "@/features/departments/hooks/useDepartmentStages";
import { CreateProjectDialog } from "@/features/projects/components/CreateProjectDialog";
import type { Project } from "@/features/projects/types";
import type { Role } from "@/lib/enums";
import { CREATOR_ROLES } from "@/lib/enums";

interface Props {
  role: Role;
  mine: boolean;
  setMine: (v: boolean) => void;
  /** Stage key (e.g. "idea") or "all" for no filter. */
  stage: string;
  setStage: (v: string) => void;
  onCreated: (p: Project) => void;
  /** Department whose stages drive the dropdown + new-project default. */
  departmentId: string;
}

export function FilterBar({
  role,
  mine,
  setMine,
  stage,
  setStage,
  onCreated,
  departmentId,
}: Props) {
  const tProj = useTranslations("projects");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { stages } = useDepartmentStages(departmentId);

  function stageLabel(s: { name_i18n: Record<string, string>; key: string }): string {
    return s.name_i18n[locale] ?? s.name_i18n.en ?? s.name_i18n.nl ?? s.key;
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-b px-4 py-3 md:px-6">
      <div className="flex items-center gap-2">
        <Switch id="mine-only" checked={mine} onCheckedChange={setMine} />
        <Label htmlFor="mine-only" className="text-sm">
          {tProj("filter_mine")}
        </Label>
      </div>

      <div className="flex items-center gap-2">
        <Label className="text-muted-foreground text-sm">{tProj("filter_stage")}</Label>
        <Select value={stage} onValueChange={setStage}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{tCommon("all")}</SelectItem>
            {stages.map((s) => (
              <SelectItem key={s.id} value={s.key}>
                {stageLabel(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="ml-auto">
        {CREATOR_ROLES.has(role) && (
          <CreateProjectDialog
            onCreated={onCreated}
            departmentId={departmentId}
            trigger={<Button size="sm">{tProj("create")}</Button>}
          />
        )}
      </div>
    </div>
  );
}
