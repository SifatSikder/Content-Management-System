"use client";

import { useDroppable } from "@dnd-kit/core";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { ProjectCard } from "@/features/projects/components/ProjectCard";
import type { Project } from "@/features/projects/types";
import { localizedStageLabel, type StageSpec } from "@/features/projects/lib/stagesByTemplate";
import { cn } from "@/lib/utils";

interface Props {
  stage: StageSpec;
  projects: Project[];
  canDrop: boolean;
}

/**
 * One column on the kanban. The displayed name comes from `stage.name_i18n`
 * (the template's label) with a fall-back to `stage.key`. Drop target id is
 * the stage's `key`, so the drag handler can forward it straight to
 * `moveStage({ stage_key })`.
 */
export function KanbanColumn({ stage, projects, canDrop }: Props) {
  const locale = useLocale();
  const tProj = useTranslations("projects");
  const { isOver, setNodeRef } = useDroppable({
    id: stage.key,
    data: { stageKey: stage.key },
    disabled: !canDrop,
  });

  const label = localizedStageLabel(stage, locale, stage.key);

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex h-full min-h-[60vh] w-[280px] flex-none snap-start flex-col rounded-lg border bg-muted/30 transition-colors",
        isOver && canDrop && "bg-accent ring-accent-foreground/20 ring-2",
      )}
    >
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-medium">{label}</span>
        <Badge variant="outline" className="text-xs">
          {projects.length}
        </Badge>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {projects.length === 0 ? (
          <p className="text-muted-foreground px-2 py-4 text-center text-xs">
            {tProj("empty_kanban")}
          </p>
        ) : (
          projects.map((p) => <ProjectCard key={p.id} project={p} draggable={canDrop} />)
        )}
      </div>
    </div>
  );
}
