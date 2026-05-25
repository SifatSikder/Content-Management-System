"use client";

import { useDroppable } from "@dnd-kit/core";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { ProjectCard } from "@/features/projects/components/ProjectCard";
import type { Stage } from "@/features/departments/types";
import type { Project } from "@/features/projects/types";
import { cn } from "@/lib/utils";

interface Props {
  stage: Stage;
  projects: Project[];
  canDrop: boolean;
}

/**
 * One column on the kanban. The displayed name comes from `stage.name_i18n`
 * (the department-editable label) with a fall-back to `stage.key` so a
 * department that just renamed a stage in another language still renders
 * cleanly. Drop target id is the stage's uuid so the drag handler can
 * forward it straight to `moveStage({ stage_id })`.
 */
export function KanbanColumn({ stage, projects, canDrop }: Props) {
  const locale = useLocale();
  const tProj = useTranslations("projects");
  const { isOver, setNodeRef } = useDroppable({
    id: stage.id,
    data: { stageId: stage.id, stageKey: stage.key },
    disabled: !canDrop,
  });

  const label =
    stage.name_i18n[locale] ?? stage.name_i18n.en ?? stage.name_i18n.nl ?? stage.key;

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
