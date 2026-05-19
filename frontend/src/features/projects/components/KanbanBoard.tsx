"use client";

import {
  DndContext,
  DragOverlay,
  PointerSensor,
  type DragEndEvent,
  type DragStartEvent,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ProjectCard } from "@/features/projects/components/ProjectCard";
import { KanbanColumn } from "@/features/projects/components/KanbanColumn";
import { moveStage } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import type { AuthUser } from "@/features/auth/types";
import { canMoveToStage, PIPELINE_STAGES, type PipelineStage } from "@/lib/enums";

import type { UseProjectsResult } from "../hooks/useProjects";

interface Props {
  user: AuthUser;
  projectsState: UseProjectsResult;
}

export function KanbanBoard({ user, projectsState }: Props) {
  const tToast = useTranslations("toast");
  const tProj = useTranslations("projects");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const [activeId, setActiveId] = useState<string | null>(null);

  const byStage = useMemo(() => {
    const map = new Map<PipelineStage, Project[]>();
    for (const stage of PIPELINE_STAGES) map.set(stage, []);
    for (const p of projectsState.projects) {
      const bucket = map.get(p.stage);
      if (bucket) bucket.push(p);
    }
    return map;
  }, [projectsState.projects]);

  const activeProject = activeId
    ? projectsState.projects.find((p) => p.id === activeId) ?? null
    : null;

  function onDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  async function onDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;
    const project = projectsState.projects.find((p) => p.id === active.id);
    if (!project) return;
    const target = over.id as PipelineStage;
    if (target === project.stage) return;
    if (!canMoveToStage(user.role, target, project.owner_id === user.id)) {
      toast.error(tProj("move_failed"));
      return;
    }
    try {
      await projectsState.optimisticUpdate(
        project.id,
        { stage: target },
        () => moveStage(project.id, target),
      );
      toast.success(tToast("stage_changed"));
    } catch {
      toast.error(tProj("move_failed"));
    }
  }

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div
        className="flex h-[calc(100vh-3.5rem-3rem)] gap-3 overflow-x-auto p-4 md:h-[calc(100vh-3.5rem)] md:snap-none [scroll-snap-type:x_mandatory]"
        aria-label="Kanban board"
      >
        {PIPELINE_STAGES.map((stage) => (
          <KanbanColumn
            key={stage}
            stage={stage}
            projects={byStage.get(stage) ?? []}
            canDrop={canMoveToStage(user.role, stage, true) || canMoveToStage(user.role, stage, false)}
          />
        ))}
      </div>
      <DragOverlay>
        {activeProject ? <ProjectCard project={activeProject} draggable={false} /> : null}
      </DragOverlay>
    </DndContext>
  );
}
