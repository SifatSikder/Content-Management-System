"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ActivityFeed } from "@/features/activity/components/ActivityFeed";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { CastingTab } from "@/features/casting/components/CastingTab";
import { EditsTab } from "@/features/edits/components/EditsTab";
import { LocationTab } from "@/features/locations/components/LocationTab";
import { BriefTab } from "@/features/projects/components/BriefTab";
import { getProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import { ScriptTab } from "@/features/scripts/components/ScriptTab";
import { ShootTab } from "@/features/shoots/components/ShootTab";
import { ApiError } from "@/lib/api-client";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const auth = useAuth();
  const tDetail = useTranslations("project_detail");
  const tStages = useTranslations("stages");
  const tCommon = useTranslations("common");

  const [project, setProject] = useState<Project | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "not_found" | "error">("loading");

  const reload = useCallback(async () => {
    if (!projectId) return;
    setStatus("loading");
    try {
      const p = await getProject(projectId);
      setProject(p);
      setStatus("ready");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setStatus("not_found");
      else setStatus("error");
    }
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (!auth.user) return null;

  if (status === "loading") {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-4 w-1/4" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (status === "not_found") {
    return <p className="text-muted-foreground p-6 text-sm">{tCommon("error")}</p>;
  }

  if (status === "error" || !project) {
    return <p className="text-muted-foreground p-6 text-sm">{tCommon("error")}</p>;
  }

  const isOwner = project.owner_id === auth.user.id;

  return (
    <div className="flex h-full flex-col">
      <header className="space-y-2 border-b px-4 py-4 md:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{project.title}</h1>
          <Badge variant="outline">{tStages(project.stage)}</Badge>
          {project.deleted_at && <Badge variant="destructive">deleted</Badge>}
        </div>
        {project.deleted_at && (
          <p className="text-muted-foreground text-sm">{tDetail("soft_deleted_banner")}</p>
        )}
      </header>

      <Tabs defaultValue="brief" className="flex flex-1 flex-col">
        <TabsList className="bg-muted/30 mx-4 mt-4 flex w-fit gap-1 overflow-x-auto md:mx-6">
          <TabsTrigger value="brief">{tDetail("tab_brief")}</TabsTrigger>
          <TabsTrigger value="script">{tDetail("tab_script")}</TabsTrigger>
          <TabsTrigger value="location">{tDetail("tab_location")}</TabsTrigger>
          <TabsTrigger value="casting">{tDetail("tab_casting")}</TabsTrigger>
          <TabsTrigger value="shoot">{tDetail("tab_shoot")}</TabsTrigger>
          <TabsTrigger value="edits">{tDetail("tab_edits")}</TabsTrigger>
          <TabsTrigger value="activity">{tDetail("tab_activity")}</TabsTrigger>
        </TabsList>

        <TabsContent value="brief" className="px-4 py-4 md:px-6">
          <BriefTab
            project={project}
            role={auth.user.role}
            isOwner={isOwner}
            onUpdated={setProject}
          />
        </TabsContent>
        <TabsContent value="script" className="px-4 py-4 md:px-6">
          <ScriptTab project={project} role={auth.user.role} isOwner={isOwner} onProjectUpdated={setProject} />
        </TabsContent>
        <TabsContent value="location" className="px-4 py-4 md:px-6">
          <LocationTab project={project} />
        </TabsContent>
        <TabsContent value="casting" className="px-4 py-4 md:px-6">
          <CastingTab project={project} />
        </TabsContent>
        <TabsContent value="shoot" className="px-4 py-4 md:px-6">
          <ShootTab project={project} />
        </TabsContent>
        <TabsContent value="edits" className="px-4 py-4 md:px-6">
          <EditsTab project={project} role={auth.user.role} isOwner={isOwner} onProjectUpdated={setProject} />
        </TabsContent>
        <TabsContent value="activity" className="px-0">
          <ActivityFeed projectId={project.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
