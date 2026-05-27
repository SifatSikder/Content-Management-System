"use client";

import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ActivityFeed } from "@/features/activity/components/ActivityFeed";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useTerminology } from "@/features/departments/hooks/useTerminology";
import { usePermissions } from "@/features/permissions/hooks/usePermissions";
import { BriefTab } from "@/features/projects/components/BriefTab";
import { useCanInputOnProject } from "@/features/projects/hooks/useCanInputOnProject";
import {
  defaultTabForStage,
  tabsForTemplate,
  type TabEntry,
} from "@/features/projects/lib/projectTabs";
import {
  getStage,
  localizedStageLabel,
} from "@/features/projects/lib/stagesByTemplate";
import { getProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

/**
 * Safe i18n lookup. next-intl throws on missing keys in dev (and renders
 * the key path in prod), so for dynamic capability labels we wrap the call
 * and fall back to the entry's English `name`.
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
 * Project detail page. The tab set is fixed by the department's
 * `template_key` (Content Creation, Marketing, …) per
 * `TABS_BY_TEMPLATE` in `features/projects/lib/projectTabs.ts`. Brief and
 * Activity are universal and bracket the per-template tabs.
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
  // Active tab is controlled so we can swap it from "brief" to the
  // stage-relevant tab *after* the permission map loads. Otherwise the
  // initial Tabs render filters with empty perms, every tab is hidden,
  // defaultValue falls back to "brief", and the user lands there.
  const [activeTab, setActiveTab] = useState<string>("brief");
  const [tabAutoSelected, setTabAutoSelected] = useState(false);

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
  const perms = usePermissions(project?.department_id);
  const canInput = useCanInputOnProject(project);

  // Once both the project and the permission map are loaded, jump to
  // the stage-relevant tab (e.g. `draft_idea` → Idea, `editing` → Edits)
  // — but only on the *first* successful load. After the user has
  // clicked any tab manually, we leave their choice alone.
  useEffect(() => {
    if (tabAutoSelected) return;
    if (!project || !perms.data) return;
    const stageTab = defaultTabForStage(
      project.department.template_key,
      project.stage_key,
    );
    if (!stageTab) {
      setTabAutoSelected(true);
      return;
    }
    const visibleTabs = tabsForTemplate(
      project.department.template_key,
    ).filter((t) => {
      if (!t.requiredAnyOf || t.requiredAnyOf.length === 0) return true;
      if (perms.data!.is_super_admin) return true;
      return t.requiredAnyOf.some((k) => perms.data!.allowed[k] === true);
    });
    if (visibleTabs.some((t) => t.key === stageTab)) {
      setActiveTab(stageTab);
    }
    setTabAutoSelected(true);
  }, [project, perms.data, tabAutoSelected]);

  function tabIsVisible(tab: TabEntry): boolean {
    if (!tab.requiredAnyOf || tab.requiredAnyOf.length === 0) return true;
    if (!perms.data) return false;
    if (perms.data.is_super_admin) return true;
    return tab.requiredAnyOf.some((k) => perms.data!.allowed[k] === true);
  }

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
  const stageSpec = getStage(project.department.template_key, project.stage_key);
  const stageLabel = localizedStageLabel(stageSpec, locale, project.stage_key);
  const tabs = tabsForTemplate(project.department.template_key).filter(tabIsVisible);
  const briefTabLabel = noun("tab_brief", tDetail("tab_brief"));
  // Treat `null` (still loading) as read-only so we don't flash an
  // editable UI before the assignee check resolves.
  const readOnly = canInput !== true;

  return (
    <div className="flex h-full flex-col">
      <header className="space-y-2 border-b px-4 py-4 md:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{project.title}</h1>
          <Badge variant="outline">{stageLabel}</Badge>
          {project.deleted_at && <Badge variant="destructive">deleted</Badge>}
          {readOnly && !project.deleted_at && (
            <Badge variant="secondary">View only</Badge>
          )}
        </div>
        {project.deleted_at && (
          <p className="text-muted-foreground text-sm">{tDetail("soft_deleted_banner")}</p>
        )}
        {readOnly && !project.deleted_at && (
          <p className="text-muted-foreground text-xs">
            You&rsquo;re not assigned to the current stage. Ask the project
            owner to add you to take action on this tab.
          </p>
        )}
      </header>

      <Tabs
        value={activeTab}
        onValueChange={(v) => {
          setActiveTab(v);
          setTabAutoSelected(true);
        }}
        className="flex flex-1 flex-col"
      >
        <TabsList className="bg-muted/30 mx-4 mt-4 flex w-fit gap-1 overflow-x-auto md:mx-6">
          <TabsTrigger value="brief">{briefTabLabel}</TabsTrigger>
          {tabs.map((cap) => (
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
            canInput={!readOnly}
            onUpdated={setProject}
          />
        </TabsContent>
        {tabs.map((cap) => {
          const role = auth.user!.role;
          return (
            <TabsContent key={cap.key} value={cap.key} className="px-4 py-4 md:px-6">
              <cap.ProjectTab
                project={project}
                role={role}
                isOwner={isOwner}
                canInput={!readOnly}
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
