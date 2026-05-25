"use client";

import { Lock, LockOpen, Save, Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ImportGdocDialog } from "@/features/script_versioning/components/ImportGdocDialog";
import { ScriptComments } from "@/features/script_versioning/components/ScriptComments";
import { ScriptEditor } from "@/features/script_versioning/components/ScriptEditor";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import {
  createVersion,
  listVersions,
  lockScript,
  submitScript,
  unlockScript,
} from "@/features/script_versioning/api";
import type { ScriptVersion } from "@/features/script_versioning/types";
import { getProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import type { Role } from "@/features/auth/constants";

const AUTOSAVE_KEY = (projectId: string) => `sre.script_draft.${projectId}`;

interface Props {
  project: Project;
  role: Role;
  isOwner: boolean;
  onProjectUpdated: (p: Project) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function ScriptTab({ project, role, isOwner, onProjectUpdated }: Props) {
  const t = useTranslations("script");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");

  const locked = project.stage.key === "script_locked";
  // Permission-service-backed gates. All three return `false` until the
  // permission map loads, hiding the affordances during that brief window
  // (strictly safer than flashing buttons the user might not have).
  const canEditAction = useCanIDo(project.department_id, "project.edit");
  const canEdit = canEditAction && !locked && !project.deleted_at;
  const canLock = useCanIDo(project.department_id, "script_versioning.lock");
  const canUnlock = useCanIDo(project.department_id, "script_versioning.unlock");

  const [versions, setVersions] = useState<ScriptVersion[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  const current = useMemo(
    () => versions.find((v) => v.id === currentId) ?? null,
    [versions, currentId],
  );
  const isOnLatest = current !== null && current === versions[versions.length - 1];

  const reload = useCallback(async () => {
    try {
      const list = await listVersions(project.id);
      setVersions(list);
      if (list.length > 0) {
        setCurrentId((prev) => prev ?? list[list.length - 1].id);
        // Hydrate draft from latest if no autosave.
        const cached = typeof window !== "undefined"
          ? window.localStorage.getItem(AUTOSAVE_KEY(project.id))
          : null;
        if (cached === null) {
          setDraft(list[list.length - 1].body_markdown ?? "");
        } else {
          setDraft(cached);
        }
      }
    } catch {
      toast.error(tErr("generic"));
    }
  }, [project.id, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Persist draft to localStorage on every change.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (draft) window.localStorage.setItem(AUTOSAVE_KEY(project.id), draft);
  }, [draft, project.id]);

  async function selectVersion(v: ScriptVersion) {
    setCurrentId(v.id);
    setDraft(v.body_markdown ?? "");
  }

  async function saveAsNewVersion() {
    setSaving(true);
    try {
      const created = await createVersion(project.id, draft);
      setVersions((prev) => [...prev, created]);
      setCurrentId(created.id);
      window.localStorage.removeItem(AUTOSAVE_KEY(project.id));
      toast.success(tToast("script_saved"));
      // Stage might have advanced (idea → script_drafting).
      const refreshed = await getProject(project.id);
      onProjectUpdated(refreshed);
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setSaving(false);
    }
  }

  async function submit() {
    try {
      await submitScript(project.id);
      const refreshed = await getProject(project.id);
      onProjectUpdated(refreshed);
      toast.success(tToast("script_submitted"));
    } catch {
      toast.error(tErr("generic"));
    }
  }

  async function doLock() {
    try {
      await lockScript(project.id);
      const refreshed = await getProject(project.id);
      onProjectUpdated(refreshed);
      toast.success(tToast("script_locked"));
    } catch {
      toast.error(tErr("generic"));
    }
  }

  async function doUnlock() {
    try {
      await unlockScript(project.id);
      const refreshed = await getProject(project.id);
      onProjectUpdated(refreshed);
      toast.success(tToast("script_unlocked"));
    } catch {
      toast.error(tErr("generic"));
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            {current ? `${t("version_label")} ${current.version_number}` : t("no_versions")}
            {locked && <Badge variant="destructive">{t("lock")}</Badge>}
          </CardTitle>
          <div className="flex flex-wrap gap-2">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm">
                  {t("version_label")} ({versions.length})
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-[360px] sm:w-[480px]">
                <SheetHeader>
                  <SheetTitle>{t("version_label")}</SheetTitle>
                </SheetHeader>
                <ul className="mt-4 space-y-2">
                  {versions.length === 0 && (
                    <p className="text-muted-foreground text-sm">{t("no_versions")}</p>
                  )}
                  {versions
                    .slice()
                    .reverse()
                    .map((v) => (
                      <li key={v.id}>
                        <button
                          type="button"
                          onClick={() => selectVersion(v)}
                          className={`hover:bg-accent w-full rounded-md border px-3 py-2 text-left text-sm ${
                            v.id === currentId ? "bg-accent" : ""
                          }`}
                        >
                          <div className="font-medium">
                            V{v.version_number}
                            {v.submitted_at && (
                              <Badge variant="secondary" className="ml-2 text-[10px]">
                                submitted
                              </Badge>
                            )}
                          </div>
                          <div className="text-muted-foreground text-xs">
                            {formatDate(v.created_at)}
                          </div>
                        </button>
                      </li>
                    ))}
                </ul>
              </SheetContent>
            </Sheet>
            {canEdit && (
              <ImportGdocDialog
                onImported={(body) => {
                  // Import loads the doc into the editor as an unsaved draft;
                  // the user clicks "Save new version" to persist (that path
                  // is also what advances the stage). If they were viewing an
                  // older version, fast-forward to the latest so the editor
                  // becomes editable for the new draft.
                  if (versions.length > 0) {
                    setCurrentId(versions[versions.length - 1].id);
                  }
                  setDraft(body);
                }}
              />
            )}
            {canEdit && (
              <Button size="sm" onClick={saveAsNewVersion} disabled={saving || !draft.trim()}>
                <Save className="mr-2 size-4" />
                {t("save_new_version")}
              </Button>
            )}
            {canEdit && project.stage.key === "script_drafting" && (
              <Button size="sm" variant="secondary" onClick={submit}>
                <Send className="mr-2 size-4" />
                {t("submit_for_review")}
              </Button>
            )}
            {!locked && canLock && versions.length > 0 && (
              <Button size="sm" variant="outline" onClick={doLock}>
                <Lock className="mr-2 size-4" />
                {t("lock")}
              </Button>
            )}
            {locked && canUnlock && (
              <Button size="sm" variant="outline" onClick={doUnlock}>
                <LockOpen className="mr-2 size-4" />
                {t("unlock")}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {locked && (
            <p className="text-muted-foreground rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
              {t("locked_banner")}
            </p>
          )}
          <ScriptEditor
            value={draft}
            onChange={setDraft}
            editable={canEdit && isOnLatest}
            placeholder={t("compose_placeholder")}
          />
          {canEdit && draft && (
            <p className="text-muted-foreground text-xs">{t("autosave")}</p>
          )}
        </CardContent>
      </Card>

      {current && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("add_comment")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ScriptComments versionId={current.id} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
