"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { FilterBar } from "@/features/projects/components/FilterBar";
import { KanbanBoard } from "@/features/projects/components/KanbanBoard";
import { useProjects } from "@/features/projects/hooks/useProjects";
import type { PipelineStage } from "@/lib/enums";

export default function ProjectsPage() {
  const tCommon = useTranslations("common");
  const tProj = useTranslations("projects");
  const auth = useAuth();
  const [mine, setMine] = useState(false);
  const [stage, setStage] = useState<PipelineStage | "all">("all");

  const projectsState = useProjects({
    filter: mine ? "mine" : undefined,
    stage: stage === "all" ? undefined : stage,
  });

  if (!auth.user) return null;

  return (
    <div className="flex h-full flex-col">
      <FilterBar
        role={auth.user.role}
        mine={mine}
        setMine={setMine}
        stage={stage}
        setStage={setStage}
        onCreated={projectsState.prepend}
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
        <KanbanBoard user={auth.user} projectsState={projectsState} />
      )}
    </div>
  );
}
