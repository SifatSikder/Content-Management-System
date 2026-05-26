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

import { useTemplateStages } from "@/features/departments/hooks/useTemplateStages";
import { ProjectCard } from "@/features/projects/components/ProjectCard";
import { KanbanColumn } from "@/features/projects/components/KanbanColumn";
import { moveStage } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import type { AuthUser } from "@/features/auth/types";

import type { UseProjectsResult } from "../hooks/useProjects";

interface Props {
  user: AuthUser;
  /** Department template_key — drives which stage list renders as columns. */
  templateKey: string | null | undefined;
  projectsState: UseProjectsResult;
}

/**
 * Template-aware kanban.
 *
 * Columns come from the in-code stage registry keyed by the department's
 * `template_key` (see `frontend/src/features/projects/lib/stagesByTemplate`).
 *
 * Drop permission is intentionally optimistic: we render every column as a
 * valid drop target and let the backend reject moves the user isn't
 * permitted to make (per `permission_service.can_user_move_to_stage`). This
 * keeps the client free of role/permission state — the permission map
 * could be folded in later via `useCanIDo("stage.move:<from>-><to>")`
 * once that's cheap to fetch per-pair.
 */
export function KanbanBoard({ user: _user, templateKey, projectsState }: Props) {
  const tToast = useTranslations("toast");
  const tProj = useTranslations("projects");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const [activeId, setActiveId] = useState<string | null>(null);
  const stages = useTemplateStages(templateKey);

  const byStage = useMemo(() => {
    const map = new Map<string, Project[]>();
    for (const s of stages) map.set(s.key, []);
    for (const p of projectsState.projects) {
      const bucket = map.get(p.stage_key);
      if (bucket) bucket.push(p);
    }
    return map;
  }, [projectsState.projects, stages]);

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
    const targetStageKey = String(over.id);
    if (targetStageKey === project.stage_key) return;
    const targetStage = stages.find((s) => s.key === targetStageKey);
    if (!targetStage) return;
    try {
      await projectsState.optimisticUpdate(
        project.id,
        { stage_key: targetStage.key },
        () => moveStage(project.id, { stage_key: targetStage.key }),
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
        {stages.map((stage) => (
          <KanbanColumn
            key={stage.key}
            stage={stage}
            projects={byStage.get(stage.key) ?? []}
            canDrop
          />
        ))}
      </div>
      <DragOverlay>
        {activeProject ? <ProjectCard project={activeProject} draggable={false} /> : null}
      </DragOverlay>
    </DndContext>
  );
}
