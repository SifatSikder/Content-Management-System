"use client";

import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ActivityFeed } from "@/features/activity/components/ActivityFeed";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { enabledCapabilities } from "@/features/capabilities/registry";
import { useTerminology } from "@/features/departments/hooks/useTerminology";
import { BriefTab } from "@/features/projects/components/BriefTab";
import { getProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

/**
 * Safe i18n lookup. next-intl throws on missing keys in dev (and renders
 * the key path in prod), so for dynamic capability labels we wrap the call
 * and fall back to the registry's English `name`.
 */
function tabLabel(
  t: (key: string) => string,
  key: string,
  fallback: string,
): string {
  try {
    return t(key);
  } catch {
    return fallback;
  }
}

/**
 * Project detail page. The tab set is dynamic: it's the intersection of
 * `project.department.capabilities` (JSONB array of capability keys) and the
 * frontend capability registry (`features/capabilities/registry.ts`).
 *
 * A department that disables a capability hides the tab but keeps the
 * backend route reachable for any in-flight UI state; the backend's
 * `require_capability` dependency 404s the underlying endpoints when the
 * dependency is wired up, so the user can't sneak around the disabled tab.
 */
export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const auth = useAuth();
  const locale = useLocale();
  const tDetail = useTranslations("project_detail");
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

  // Hooks MUST be called on every render in the same order — keep them above
  // the conditional early returns. `useTerminology` tolerates `undefined`
  // and just returns a noun-fallback identity while the project loads.
  const noun = useTerminology(project?.department.terminology);

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
  const stageLabel =
    project.stage.name_i18n[locale] ??
    project.stage.name_i18n.en ??
    project.stage.name_i18n.nl ??
    project.stage.key;
  const capabilities = enabledCapabilities(project.department.capabilities);
  const briefTabLabel = noun("tab_brief", tDetail("tab_brief"));

  return (
    <div className="flex h-full flex-col">
      <header className="space-y-2 border-b px-4 py-4 md:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{project.title}</h1>
          <Badge variant="outline">{stageLabel}</Badge>
          {project.deleted_at && <Badge variant="destructive">deleted</Badge>}
        </div>
        {project.deleted_at && (
          <p className="text-muted-foreground text-sm">{tDetail("soft_deleted_banner")}</p>
        )}
      </header>

      <Tabs defaultValue="brief" className="flex flex-1 flex-col">
        <TabsList className="bg-muted/30 mx-4 mt-4 flex w-fit gap-1 overflow-x-auto md:mx-6">
          <TabsTrigger value="brief">{briefTabLabel}</TabsTrigger>
          {capabilities.map((cap) => (
            <TabsTrigger key={cap.key} value={cap.key}>
              {tabLabel(tDetail, cap.tabLabelKey, cap.name)}
            </TabsTrigger>
          ))}
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
        {capabilities.map((cap) => {
          const role = auth.user!.role;
          return (
            <TabsContent key={cap.key} value={cap.key} className="px-4 py-4 md:px-6">
              <cap.ProjectTab
                project={project}
                role={role}
                isOwner={isOwner}
                onProjectUpdated={setProject}
              />
            </TabsContent>
          );
        })}
        <TabsContent value="activity" className="px-0">
          <ActivityFeed projectId={project.id} departmentId={project.department_id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
