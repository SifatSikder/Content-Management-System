"use client";

import { Lock, LockOpen, Pencil, Save, Send, X } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  createIdeaVersion,
  getIdeaSummary,
  listIdeaVersions,
  lockIdea,
  unlockIdea,
  updateIdeaVersion,
} from "@/features/idea_versioning/api";
import { RequestFeedbackDialog } from "@/features/idea_versioning/components/RequestFeedbackDialog";
import { SignoffPanel } from "@/features/idea_versioning/components/SignoffPanel";
import type {
  IdeaSummary,
  IdeaVersion,
} from "@/features/idea_versioning/types";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
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

export function IdeaTab({ project, canInput = true, onProjectUpdated }: Props) {
  const { data: session } = useSession();
  const currentUserId = (session?.user as { id?: string } | undefined)?.id ?? "";

  const [summary, setSummary] = useState<IdeaSummary | null>(null);
  const [versions, setVersions] = useState<IdeaVersion[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [requestDialogOpen, setRequestDialogOpen] = useState(false);
  // Explicit edit-toggle so the default view of the current version is
  // read-only — the textarea only appears once the owner clicks Edit
  // draft. Otherwise the page always looks "editing" and the saved
  // state is invisible.
  const [editingInPlace, setEditingInPlace] = useState(false);

  const canEdit =
    useCanIDo(project.department_id, "project.edit") && canInput;
  const canLock =
    useCanIDo(project.department_id, "idea_versioning.lock") && canInput;
  const isOwner = currentUserId !== "" && currentUserId === project.owner_id;

  async function load() {
    try {
      const [s, vs] = await Promise.all([
        getIdeaSummary(project.id),
        listIdeaVersions(project.id),
      ]);
      setSummary(s);
      setVersions(vs);
    } catch {
      toast.error("Failed to load idea");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  // Edit-in-place mode: owner, idea not locked, no reviewers yet,
  // there's a current version. While true, the textarea is pre-filled
  // with the current body and saving PATCHes the same version instead
  // of creating a new V.
  const canEditInPlace =
    isOwner &&
    !!summary &&
    summary.locked_at === null &&
    summary.latest_version !== null &&
    summary.reviewer_count === 0;

  // Edit-in-place is no longer the default view; opening it requires an
  // explicit click. The moment that mode is no longer available (idea
  // locked, reviewers pulled in, ownership change), drop out of it so
  // the read-only view shows again.
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
      toast.error("Idea body cannot be empty");
      return;
    }
    setBusy(true);
    try {
      await createIdeaVersion(project.id, { body_markdown: body });
      toast.success("New idea version saved");
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
      toast.error("Idea body cannot be empty");
      return;
    }
    setBusy(true);
    try {
      await updateIdeaVersion(project.id, summary.latest_version.id, body);
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
      const next = await lockIdea(project.id);
      setSummary(next);
      toast.success("Idea locked — project advanced to Script drafting");
      // Page-level reload of project to pick up the new stage_key.
      onProjectUpdated?.({ ...project, stage_key: "script_drafting" });
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to lock idea",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleUnlock() {
    setBusy(true);
    try {
      const next = await unlockIdea(project.id);
      setSummary(next);
      toast.success("Idea unlocked — you can edit or save a new version");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to unlock idea",
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
              Idea locked
            </Badge>
            {isOwner ? (
              <Button
                variant="outline"
                onClick={handleUnlock}
                disabled={busy}
                title="Reopen the idea so you can edit it or save a new version"
              >
                <LockOpen className="size-4" />
                Unlock idea
              </Button>
            ) : null}
          </>
        ) : canLock ? (
          <Button
            onClick={handleLock}
            disabled={busy || !summary.can_lock}
            title={
              summary.can_lock
                ? "Lock the idea and advance to Script drafting"
                : `${summary.pending_reviewer_ids.length} reviewer(s) still need to approve`
            }
          >
            <Lock className="size-4" />
            Lock idea
          </Button>
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
                <Textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={8}
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
              <pre className="bg-muted/40 max-h-72 overflow-auto rounded-md p-3 text-sm whitespace-pre-wrap">
                {latest.body_markdown}
              </pre>
            )}
            {!canEditInPlace ? (
              <SignoffPanel
                project={project}
                versionId={latest.id}
                signoffs={summary.latest_version_signoffs}
                currentUserId={currentUserId}
                onSignoffAdded={() => void load()}
              />
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {!locked && canEdit && !latest ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Draft idea V1</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={8}
              placeholder="Sketch the first version of the idea here. Markdown is fine."
            />
            <Button
              onClick={handleSaveVersion}
              disabled={busy || !draft.trim()}
            >
              <Save className="size-4" />
              Save as V1
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {!locked && canEdit && latest && !canEditInPlace ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Draft idea V{latest.version_number + 1}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={8}
              placeholder="Revise based on the feedback above and save a new version…"
            />
            <Button
              onClick={handleSaveVersion}
              disabled={busy || !draft.trim()}
            >
              <Save className="size-4" />
              Save as V{latest.version_number + 1}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {!latest ? (
        <p className="text-muted-foreground text-sm">
          No idea version yet. Save the first draft above to kick off the
          review loop.
        </p>
      ) : null}

      {versions.length > 1 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Version history</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-xs">
              {versions
                .slice()
                .sort((a, b) => b.version_number - a.version_number)
                .map((v) => (
                  <li key={v.id} className="flex items-center justify-between">
                    <span>V{v.version_number}</span>
                    <span className="text-muted-foreground">
                      {formatDate(v.created_at)}
                    </span>
                  </li>
                ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <RequestFeedbackDialog
        project={project}
        open={requestDialogOpen}
        onOpenChange={setRequestDialogOpen}
        onRequested={() => void load()}
      />
    </div>
  );
}
