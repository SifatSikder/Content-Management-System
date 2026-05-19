"use client";

import { useDroppable } from "@dnd-kit/core";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { ProjectCard } from "@/features/projects/components/ProjectCard";
import type { Project } from "@/features/projects/types";
import type { PipelineStage } from "@/lib/enums";
import { cn } from "@/lib/utils";

interface Props {
  stage: PipelineStage;
  projects: Project[];
  canDrop: boolean;
}

export function KanbanColumn({ stage, projects, canDrop }: Props) {
  const t = useTranslations("stages");
  const tProj = useTranslations("projects");
  const { isOver, setNodeRef } = useDroppable({
    id: stage,
    data: { stage },
    disabled: !canDrop,
  });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex h-full min-h-[60vh] w-[280px] flex-none snap-start flex-col rounded-lg border bg-muted/30 transition-colors",
        isOver && canDrop && "bg-accent ring-accent-foreground/20 ring-2",
      )}
    >
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-medium">{t(stage)}</span>
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
