"use client";

import { Lock, Save, Send } from "lucide-react";
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
  requestIdeaEnhancement,
} from "@/features/idea_versioning/api";
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

  async function handleRequestEnhancement() {
    setBusy(true);
    try {
      const res = await requestIdeaEnhancement(project.id);
      const n = res.newly_assigned_user_ids.length;
      toast.success(
        n > 0
          ? `Feedback requested — ${n} reviewer(s) notified by email`
          : "All reviewers were already assigned",
      );
      await load();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to request feedback",
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
            onClick={handleRequestEnhancement}
            disabled={busy}
            title="Pull CEO + Director onto this card and email them"
          >
            <Send className="size-4" />
            Request feedback
          </Button>
        ) : null}
        {locked ? (
          <Badge variant="secondary" className="gap-1">
            <Lock className="size-3" />
            Idea locked
          </Badge>
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

      {!locked && canEdit ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {latest ? `Draft idea V${latest.version_number + 1}` : "Draft idea V1"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={8}
              placeholder={
                latest
                  ? "Revise based on the feedback above and save a new version…"
                  : "Sketch the first version of the idea here. Markdown is fine."
              }
            />
            <Button onClick={handleSaveVersion} disabled={busy || !draft.trim()}>
              <Save className="size-4" />
              {latest
                ? `Save as V${latest.version_number + 1}`
                : "Save as V1"}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {latest ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">
              Current version (V{latest.version_number})
            </CardTitle>
            <span className="text-muted-foreground text-xs">
              {formatDate(latest.created_at)}
            </span>
          </CardHeader>
          <CardContent className="space-y-4">
            <pre className="bg-muted/40 max-h-72 overflow-auto rounded-md p-3 text-sm whitespace-pre-wrap">
              {latest.body_markdown}
            </pre>
            <SignoffPanel
              project={project}
              versionId={latest.id}
              signoffs={summary.latest_version_signoffs}
              currentUserId={currentUserId}
              onSignoffAdded={() => void load()}
            />
          </CardContent>
        </Card>
      ) : (
        <p className="text-muted-foreground text-sm">
          No idea version yet. Save the first draft above to kick off the
          review loop.
        </p>
      )}

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
    </div>
  );
}
