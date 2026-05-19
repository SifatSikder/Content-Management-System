"use client";

import { CheckCircle2, MessageSquareWarning, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { getProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import {
  approveEdit,
  listEditComments,
  listEdits,
  requestChanges,
} from "@/features/edits/api";
import { EditCommentsList } from "@/features/edits/components/EditCommentsList";
import { UploadDialog } from "@/features/edits/components/UploadDialog";
import {
  VideoReviewPlayer,
  type VideoReviewPlayerHandle,
} from "@/features/edits/components/VideoReviewPlayer";
import type { EditComment, EditVersion } from "@/features/edits/types";
import {
  APPROVER_ROLES,
  CHANGE_REQUESTER_ROLES,
  canEditProject,
  type Role,
} from "@/lib/enums";

interface Props {
  project: Project;
  role: Role;
  isOwner: boolean;
  onProjectUpdated: (p: Project) => void;
}

export function EditsTab({ project, role, isOwner, onProjectUpdated }: Props) {
  const t = useTranslations("edits");
  const tCommon = useTranslations("common");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");

  const [edits, setEdits] = useState<EditVersion[] | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [comments, setComments] = useState<EditComment[]>([]);
  const [changesNote, setChangesNote] = useState("");
  const playerRef = useRef<VideoReviewPlayerHandle | null>(null);

  const current = useMemo(
    () => edits?.find((e) => e.id === currentId) ?? null,
    [edits, currentId],
  );
  const latest = useMemo(() => (edits && edits.length ? edits[edits.length - 1] : null), [edits]);
  const canUpload = canEditProject(role, isOwner) && !project.deleted_at;

  const reload = useCallback(async () => {
    try {
      const list = await listEdits(project.id);
      setEdits(list);
      if (list.length > 0) {
        setCurrentId((prev) => prev ?? list[list.length - 1].id);
      } else {
        setCurrentId(null);
      }
    } catch {
      toast.error(tErr("generic"));
    }
  }, [project.id, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!currentId) {
      setComments([]);
      return;
    }
    let cancelled = false;
    void listEditComments(currentId).then((list) => {
      if (!cancelled) setComments(list);
    });
    return () => {
      cancelled = true;
    };
  }, [currentId]);

  async function refreshProject() {
    try {
      const updated = await getProject(project.id);
      onProjectUpdated(updated);
    } catch {
      /* ignore */
    }
  }

  async function doApprove() {
    if (!current) return;
    try {
      const updated = await approveEdit(current.id);
      setEdits((prev) => (prev ?? []).map((e) => (e.id === updated.id ? updated : e)));
      toast.success(tToast("edit_approved"));
      await refreshProject();
    } catch {
      toast.error(tErr("generic"));
    }
  }

  async function doRequestChanges() {
    if (!current || !changesNote.trim()) return;
    try {
      const updated = await requestChanges(current.id, changesNote.trim());
      setEdits((prev) => (prev ?? []).map((e) => (e.id === updated.id ? updated : e)));
      toast.success(tToast("edit_changes_requested"));
      setChangesNote("");
      await refreshProject();
    } catch {
      toast.error(tErr("generic"));
    }
  }

  if (edits === null) {
    return <Skeleton className="h-72 w-full" />;
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t("upload_cv")}</CardTitle>
          {canUpload && (
            <UploadDialog
              projectId={project.id}
              previousVersion={latest}
              onUploaded={async (edit) => {
                setEdits((prev) => [...(prev ?? []), edit]);
                setCurrentId(edit.id);
                await refreshProject();
              }}
              trigger={
                <Button size="sm">
                  <Upload className="mr-2 size-4" />
                  {t("upload_cv")}
                </Button>
              }
            />
          )}
        </CardHeader>
        <CardContent>
          {edits.length === 0 ? (
            <p className="text-muted-foreground text-sm">{t("no_edits")}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {edits.map((e) => (
                <Button
                  key={e.id}
                  variant={e.id === currentId ? "default" : "outline"}
                  size="sm"
                  onClick={() => setCurrentId(e.id)}
                  className="gap-2"
                >
                  {t("version_n", { n: e.version_number })}
                  {e.status === "approved" && (
                    <Badge variant="secondary" className="text-[10px]">
                      ✓
                    </Badge>
                  )}
                  {e.status === "changes_requested" && (
                    <Badge variant="destructive" className="text-[10px]">
                      !
                    </Badge>
                  )}
                </Button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {current && (
        <Card>
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">
              {t("version_n", { n: current.version_number })}
              <Badge variant="outline" className="ml-2">
                {current.status}
              </Badge>
            </CardTitle>
            <div className="flex gap-2">
              {CHANGE_REQUESTER_ROLES.has(role) && current.status !== "approved" && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="sm">
                      <MessageSquareWarning className="mr-2 size-4" />
                      {t("request_changes")}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t("request_changes_title")}</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t("request_changes_body")}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <Textarea
                      rows={3}
                      value={changesNote}
                      onChange={(e) => setChangesNote(e.target.value)}
                    />
                    <AlertDialogFooter>
                      <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                      <AlertDialogAction onClick={doRequestChanges} disabled={!changesNote.trim()}>
                        {t("request_changes")}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
              {APPROVER_ROLES.has(role) && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button size="sm">
                      <CheckCircle2 className="mr-2 size-4" />
                      {t("approve")}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t("approve_title")}</AlertDialogTitle>
                      <AlertDialogDescription>{t("approve_body")}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                      <AlertDialogAction onClick={doApprove}>{t("approve")}</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {current.notes && (
              <p className="bg-muted/40 rounded-md border p-2 text-sm">{current.notes}</p>
            )}
            <VideoReviewPlayer
              ref={playerRef}
              edit={current}
              comments={comments}
              onCommentAdded={(c) => setComments((prev) => [...prev, c])}
            />
            <EditCommentsList
              comments={comments}
              onUpdate={(c) =>
                setComments((prev) => prev.map((existing) => (existing.id === c.id ? c : existing)))
              }
              onJumpTo={(seconds) => playerRef.current?.seekTo(seconds)}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
