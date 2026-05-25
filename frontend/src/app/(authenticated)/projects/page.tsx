"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useCurrentDepartment } from "@/features/departments/hooks/useCurrentDepartment";
import { FilterBar } from "@/features/projects/components/FilterBar";
import { KanbanBoard } from "@/features/projects/components/KanbanBoard";
import { useProjects } from "@/features/projects/hooks/useProjects";

export default function ProjectsPage() {
  const tCommon = useTranslations("common");
  const tProj = useTranslations("projects");
  const auth = useAuth();
  const department = useCurrentDepartment();
  const [mine, setMine] = useState(false);
  const [stageKey, setStageKey] = useState<string>("all");

  const projectsState = useProjects({
    filter: mine ? "mine" : undefined,
    stage: stageKey === "all" ? undefined : stageKey,
  });

  if (!auth.user) return null;

  if (department.status === "loading") {
    return (
      <div className="flex gap-3 overflow-x-auto p-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="w-[280px] flex-none space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (department.status === "none" || !department.current) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground text-sm">{tProj("no_department")}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <FilterBar
        role={auth.user.role}
        mine={mine}
        setMine={setMine}
        stage={stageKey}
        setStage={setStageKey}
        onCreated={projectsState.prepend}
        departmentId={department.current.id}
      />

      {projectsState.status === "loading" ? (
        <div className="flex gap-3 overflow-x-auto p-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="w-[280px] flex-none space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ))}
        </div>
      ) : projectsState.status === "error" ? (
        <div className="p-6 text-center">
          <p className="text-muted-foreground text-sm">{tProj("load_error")}</p>
          <Button variant="outline" className="mt-3" onClick={() => projectsState.reload()}>
            {tCommon("retry")}
          </Button>
        </div>
      ) : (
        <KanbanBoard
          user={auth.user}
          departmentId={department.current.id}
          projectsState={projectsState}
        />
      )}
    </div>
  );
}
