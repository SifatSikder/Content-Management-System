"use client";

import { Lock, LockOpen, Pencil, Save, Send, X } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ImportGdocDialog } from "@/features/script_versioning/components/ImportGdocDialog";
import { ScriptEditor } from "@/features/script_versioning/components/ScriptEditor";
import { ScriptRequestFeedbackDialog } from "@/features/script_versioning/components/ScriptRequestFeedbackDialog";
import { ScriptSignoffPanel } from "@/features/script_versioning/components/ScriptSignoffPanel";
import { ScriptVersionHistoryItem } from "@/features/script_versioning/components/ScriptVersionHistoryItem";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import {
  createVersion,
  getScriptSummary,
  listVersions,
  lockScript,
  unlockScript,
  updateVersion,
} from "@/features/script_versioning/api";
import type {
  ScriptSummary,
  ScriptVersion,
} from "@/features/script_versioning/types";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  project: Project;
  canInput?: boolean;
  onProjectUpdated?: (next: Project) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function ScriptTab({ project, canInput = true, onProjectUpdated }: Props) {
  const { data: session } = useSession();
  const currentUserId = (session?.user as { id?: string } | undefined)?.id ?? "";

  const [summary, setSummary] = useState<ScriptSummary | null>(null);
  const [versions, setVersions] = useState<ScriptVersion[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestDialogOpen, setRequestDialogOpen] = useState(false);
  const [editingInPlace, setEditingInPlace] = useState(false);
  const [reloadCounter, setReloadCounter] = useState(0);

  const canEdit =
    useCanIDo(project.department_id, "project.edit") && canInput;
  const hasLockPerm =
    useCanIDo(project.department_id, "script_versioning.lock") && canInput;
  const isOwner = currentUserId !== "" && currentUserId === project.owner_id;
  // Lock + Unlock are owner-only — even if CEO/Director hold the
  // permission, only the script owner decides when the draft is done.
  const canLock = isOwner && hasLockPerm;

  async function load() {
    try {
      const [s, vs] = await Promise.all([
        getScriptSummary(project.id),
        listVersions(project.id),
      ]);
      setSummary(s);
      setVersions(vs);
      setReloadCounter((c) => c + 1);
    } catch {
      toast.error("Failed to load script");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  // Edit-in-place mode: owner, script not locked, current version has
  // no signoffs on it yet. Once a reviewer engages the version, the
  // next edit becomes a new version.
  const canEditInPlace =
    isOwner &&
    !!summary &&
    summary.locked_at === null &&
    summary.latest_version !== null &&
    summary.latest_version_signoffs.length === 0;

  useEffect(() => {
    if (!canEditInPlace && editingInPlace) {
      setEditingInPlace(false);
    }
  }, [canEditInPlace, editingInPlace]);

  function startEditInPlace() {
    if (!summary?.latest_version) return;
    setDraft(summary.latest_version.body_markdown);
    setEditingInPlace(true);
  }

  function cancelEditInPlace() {
    setEditingInPlace(false);
    setDraft("");
  }

  async function handleSaveVersion() {
    const body = draft.trim();
    if (!body) {
      toast.error("Script body cannot be empty");
      return;
    }
    setBusy(true);
    try {
      await createVersion(project.id, body);
      toast.success("New script version saved");
      setDraft("");
      await load();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to save version",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveInPlace() {
    if (!summary?.latest_version) return;
    const body = draft.trim();
    if (!body) {
      toast.error("Script body cannot be empty");
      return;
    }
    setBusy(true);
    try {
      await updateVersion(project.id, summary.latest_version.id, body);
      toast.success("Draft saved");
      setEditingInPlace(false);
      setDraft("");
      await load();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to save draft",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleLock() {
    setBusy(true);
    try {
      const next = await lockScript(project.id);
      setSummary(next);
      toast.success("Script locked — project advanced to Casting");
      onProjectUpdated?.({
        ...project,
        stage_key: "casting",
        script_locked_at: next.locked_at,
        script_locked_by: next.locked_by,
      });
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to lock script",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleUnlock() {
    setBusy(true);
    try {
      const next = await unlockScript(project.id);
      setSummary(next);
      toast.success("Script unlocked — you can edit or save a new version");
      const stagePatch: Partial<Project> = {
        script_locked_at: null,
        script_locked_by: null,
      };
      if (project.stage_key === "casting") {
        stagePatch.stage_key = "script_drafting";
      }
      onProjectUpdated?.({ ...project, ...stagePatch });
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to unlock script",
      );
    } finally {
      setBusy(false);
    }
  }

  if (summary === null || versions === null) {
    return <p className="text-muted-foreground text-sm">Loading…</p>;
  }

  const locked = summary.locked_at !== null;
  const latest = summary.latest_version;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-2">
        {!locked && isOwner && latest ? (
          <Button
            variant="outline"
            onClick={() => setRequestDialogOpen(true)}
            disabled={busy}
            title="Pick which CEO/Director members to ping for feedback"
          >
            <Send className="size-4" />
            Request feedback
          </Button>
        ) : null}
        {locked ? (
          <>
            <Badge variant="secondary" className="gap-1">
              <Lock className="size-3" />
              Script locked
            </Badge>
            {isOwner ? (
              <Button
                variant="outline"
                onClick={handleUnlock}
                disabled={busy}
                title="Reopen the script so you can edit it or save a new version"
              >
                <LockOpen className="size-4" />
                Unlock script
              </Button>
            ) : null}
          </>
        ) : canLock ? (
          <TooltipProvider delayDuration={150}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className={summary.can_lock ? undefined : "cursor-not-allowed"}>
                  <Button
                    onClick={handleLock}
                    disabled={busy || !summary.can_lock}
                    className={summary.can_lock ? undefined : "pointer-events-none"}
                  >
                    <Lock className="size-4" />
                    Lock script
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {summary.can_lock
                  ? "Lock the script and advance to Casting"
                  : summary.latest_version &&
                      summary.latest_version.submitted_at === null
                    ? "Send this version for review first (Request feedback)"
                    : `${summary.pending_reviewer_ids.length} reviewer(s) still need to approve`}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : null}
      </div>

      {latest ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">
              {editingInPlace
                ? `Editing V${latest.version_number}`
                : `Current version (V${latest.version_number})`}
            </CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground text-xs">
                {formatDate(latest.created_at)}
              </span>
              {canEditInPlace && !editingInPlace ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={startEditInPlace}
                  disabled={busy}
                  title="Edit the current version in place — no new version is created until you request feedback"
                >
                  <Pencil className="size-3" />
                  Edit draft
                </Button>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {editingInPlace ? (
              <>
                <ScriptEditor
                  value={draft}
                  onChange={setDraft}
                  editable={true}
                  placeholder="Edit your draft in place. Saving overwrites the current version until you request feedback."
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={handleSaveInPlace}
                    disabled={
                      busy ||
                      !draft.trim() ||
                      draft === latest.body_markdown
                    }
                  >
                    <Save className="size-4" />
                    Save changes
                  </Button>
                  <ImportGdocDialog
                    onImported={(body) => setDraft(body)}
                  />
                  <Button
                    variant="ghost"
                    onClick={cancelEditInPlace}
                    disabled={busy}
                  >
                    <X className="size-4" />
                    Cancel
                  </Button>
                </div>
              </>
            ) : (
              <ScriptEditor
                value={latest.body_markdown}
                onChange={() => {}}
                editable={false}
                placeholder=""
              />
            )}
            {!canEditInPlace ? (
              latest.submitted_at !== null ? (
                <ScriptSignoffPanel
                  project={project}
                  versionId={latest.id}
                  signoffs={summary.latest_version_signoffs}
                  currentUserId={currentUserId}
                  onSignoffAdded={() => void load()}
                  refreshKey={reloadCounter}
                />
              ) : (
                <p className="text-muted-foreground rounded-md border border-dashed p-3 text-sm">
                  {isOwner
                    ? "This version is a draft. Click Request feedback when you're ready to send it for review."
                    : "The owner is preparing this version. You'll be notified by email when it's ready for review."}
                </p>
              )
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {!locked && canEdit && isOwner && !latest ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Draft script V1</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ScriptEditor
              value={draft}
              onChange={setDraft}
              editable={true}
              placeholder="Sketch the first version of the script here. Import from Google Docs if you've drafted it there."
            />
            <div className="flex items-center gap-2">
              <Button
                onClick={handleSaveVersion}
                disabled={busy || !draft.trim()}
              >
                <Save className="size-4" />
                Save as V1
              </Button>
              <ImportGdocDialog onImported={(body) => setDraft(body)} />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!locked && canEdit && isOwner && latest && !canEditInPlace ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Draft script V{latest.version_number + 1}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ScriptEditor
              value={draft}
              onChange={setDraft}
              editable={true}
              placeholder="Revise based on the feedback above and save a new version…"
            />
            <div className="flex items-center gap-2">
              <Button
                onClick={handleSaveVersion}
                disabled={busy || !draft.trim()}
              >
                <Save className="size-4" />
                Save as V{latest.version_number + 1}
              </Button>
              <ImportGdocDialog onImported={(body) => setDraft(body)} />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!latest && isOwner ? (
        <p className="text-muted-foreground text-sm">
          No script version yet. Save the first draft above to kick off the
          review loop.
        </p>
      ) : !latest ? (
        <p className="text-muted-foreground text-sm">
          The project owner hasn&apos;t drafted a script yet.
        </p>
      ) : null}

      {versions.length > 1 && isOwner ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Version history</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {versions
                .slice()
                .sort((a, b) => b.version_number - a.version_number)
                .map((v) => (
                  <ScriptVersionHistoryItem
                    key={v.id}
                    projectId={project.id}
                    version={v}
                  />
                ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <ScriptRequestFeedbackDialog
        project={project}
        open={requestDialogOpen}
        onOpenChange={setRequestDialogOpen}
        onRequested={() => void load()}
      />
    </div>
  );
}
