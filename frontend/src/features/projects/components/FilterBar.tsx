"use client";

import { useTranslations } from "next-intl";

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
import { PIPELINE_STAGES, type PipelineStage } from "@/lib/enums";
import { CreateProjectDialog } from "@/features/projects/components/CreateProjectDialog";
import type { Project } from "@/features/projects/types";
import type { Role } from "@/lib/enums";
import { CREATOR_ROLES } from "@/lib/enums";

interface Props {
  role: Role;
  mine: boolean;
  setMine: (v: boolean) => void;
  stage: PipelineStage | "all";
  setStage: (v: PipelineStage | "all") => void;
  onCreated: (p: Project) => void;
}

export function FilterBar({ role, mine, setMine, stage, setStage, onCreated }: Props) {
  const tProj = useTranslations("projects");
  const tStages = useTranslations("stages");
  const tCommon = useTranslations("common");

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
        <Select value={stage} onValueChange={(v) => setStage(v as PipelineStage | "all")}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{tCommon("all")}</SelectItem>
            {PIPELINE_STAGES.map((s) => (
              <SelectItem key={s} value={s}>
                {tStages(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="ml-auto">
        {CREATOR_ROLES.has(role) && (
          <CreateProjectDialog
            onCreated={onCreated}
            trigger={<Button size="sm">{tProj("create")}</Button>}
          />
        )}
      </div>
    </div>
  );
}
