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

import { useDepartmentStages } from "@/features/departments/hooks/useDepartmentStages";
import { ProjectCard } from "@/features/projects/components/ProjectCard";
import { KanbanColumn } from "@/features/projects/components/KanbanColumn";
import { moveStage } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import type { AuthUser } from "@/features/auth/types";

import type { UseProjectsResult } from "../hooks/useProjects";

interface Props {
  user: AuthUser;
  /** The department whose stages drive the kanban columns. */
  departmentId: string;
  projectsState: UseProjectsResult;
}

/**
 * Department-aware kanban.
 *
 * Columns come from `/departments/{id}/stages` (rather than the legacy
 * hard-coded `PIPELINE_STAGES` enum) so a CEO who renames "Idea" to "Brief"
 * sees the change after a refresh without redeploying code.
 *
 * Drop permission is intentionally optimistic: we render every column as a
 * valid drop target and let the backend reject moves the user isn't
 * permitted to make (per `permission_service.can_user_move_to_stage`). This
 * keeps the client free of role/permission state — the permission map
 * could be folded in later via `useCanIDo("stage.move:<from>-><to>")`
 * once that's cheap to fetch per-pair.
 */
export function KanbanBoard({ user: _user, departmentId, projectsState }: Props) {
  const tToast = useTranslations("toast");
  const tProj = useTranslations("projects");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const [activeId, setActiveId] = useState<string | null>(null);
  const { stages } = useDepartmentStages(departmentId);

  const byStage = useMemo(() => {
    const map = new Map<string, Project[]>();
    for (const s of stages) map.set(s.id, []);
    for (const p of projectsState.projects) {
      const bucket = map.get(p.stage_id);
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
    const targetStageId = String(over.id);
    if (targetStageId === project.stage_id) return;
    const targetStage = stages.find((s) => s.id === targetStageId);
    if (!targetStage) return;
    try {
      await projectsState.optimisticUpdate(
        project.id,
        {
          stage_id: targetStage.id,
          stage: {
            id: targetStage.id,
            key: targetStage.key,
            name_i18n: targetStage.name_i18n,
            order_index: targetStage.order_index,
            is_terminal: targetStage.is_terminal,
            color: targetStage.color,
          },
        },
        () => moveStage(project.id, { stage_id: targetStage.id }),
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
            key={stage.id}
            stage={stage}
            projects={byStage.get(stage.id) ?? []}
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
