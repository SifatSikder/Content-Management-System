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
import type { Role } from "@/features/auth/constants";
import { useDepartmentStages } from "@/features/departments/hooks/useDepartmentStages";
import { useTerminology } from "@/features/departments/hooks/useTerminology";
import type { Terminology } from "@/features/departments/types";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import { CreateProjectDialog } from "@/features/projects/components/CreateProjectDialog";
import type { Project } from "@/features/projects/types";

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
  /**
   * Department's terminology JSONB. When the template carries an override
   * (Marketing has `create_project = "New lead"`), the create button label
   * picks that up; otherwise it falls back to `projects.create`.
   */
  terminology?: Terminology;
}

export function FilterBar({
  role: _role,
  mine,
  setMine,
  stage,
  setStage,
  onCreated,
  departmentId,
  terminology,
}: Props) {
  const tProj = useTranslations("projects");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const noun = useTerminology(terminology);
  const { stages } = useDepartmentStages(departmentId);
  // Hidden until the permission map loads; same tradeoff as ScriptTab.
  const canCreate = useCanIDo(departmentId, "project.create");

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
        {canCreate && (
          <CreateProjectDialog
            onCreated={onCreated}
            departmentId={departmentId}
            trigger={
              <Button size="sm">{noun("create_project", tProj("create"))}</Button>
            }
          />
        )}
      </div>
    </div>
  );
}
