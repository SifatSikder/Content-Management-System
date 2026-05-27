"use client";

import { CheckCircle2, MessageSquareWarning, Send, Sparkles, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
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
import { getProject, listStageAssignees } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import {
  approveEdit,
  dispatchEditComments,
  getEditApprovals,
  listEditComments,
  listEdits,
  requestChanges,
} from "@/features/asset_review_with_timecodes/api";
import { EditApprovalPanel } from "@/features/asset_review_with_timecodes/components/EditApprovalPanel";
import { EditCommentsList } from "@/features/asset_review_with_timecodes/components/EditCommentsList";
import { RawCutsByShoot } from "@/features/asset_review_with_timecodes/components/RawCutsByShoot";
import { UploadDialog } from "@/features/asset_review_with_timecodes/components/UploadDialog";
import {
  VideoReviewPlayer,
  type VideoReviewPlayerHandle,
} from "@/features/asset_review_with_timecodes/components/VideoReviewPlayer";
import type {
  EditApprovalSummary,
  EditComment,
  EditVersion,
} from "@/features/asset_review_with_timecodes/types";
import { ApiError } from "@/lib/api-client";
import { useCanIDo } from "@/features/permissions/hooks/usePermissions";
import type { Role } from "@/features/auth/constants";

interface Props {
  project: Project;
  role: Role;
  isOwner: boolean;
  canInput?: boolean;
  onProjectUpdated: (p: Project) => void;
}

export function EditsTab({
  project,
  role,
  isOwner,
  canInput = true,
  onProjectUpdated,
}: Props) {
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
  // Permission-service-backed gates. All return `false` until the
  // permission map loads (same tradeoff as ScriptTab's lock gates).
  // Approve is handled inside <EditApprovalPanel/> now (per-reviewer
  // gate from the new approval-summary endpoint), so we don't compute
  // a `canApprove` here anymore.
  const canEditAction =
    useCanIDo(project.department_id, "project.edit") && canInput;
  const canRequestChanges =
    useCanIDo(
      project.department_id,
      "asset_review_with_timecodes.request_changes",
    ) && canInput;
  // Uploading a new cut is editor-only — gated on active assignment to
  // the `editing` stage rather than the broad `project.edit` perm
  // (CEO/Asst CEO/Director all hold that perm but shouldn't upload
  // cuts themselves; they review what the editor delivers).
  const { data: session } = useSession();
  const currentUserId = (session?.user as { id?: string } | undefined)?.id ?? "";
  const [isEditorAssignee, setIsEditorAssignee] = useState(false);
  useEffect(() => {
    let cancelled = false;
    if (!currentUserId) {
      setIsEditorAssignee(false);
      return;
    }
    (async () => {
      try {
        const res = await listStageAssignees(project.id, "editing");
        if (cancelled) return;
        setIsEditorAssignee(
          res.items.some((a) => a.user_id === currentUserId),
        );
      } catch {
        if (cancelled) return;
        setIsEditorAssignee(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [project.id, currentUserId]);
  const canUpload =
    isEditorAssignee &&
    canEditAction &&
    !project.deleted_at &&
    project.stage_key !== "approved_published";

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

  // Lift the approval summary up so the parent action bar can
  // coordinate the Send + Approve buttons (mutually disabled state).
  const [approvalSummary, setApprovalSummary] =
    useState<EditApprovalSummary | null>(null);
  const [actionBusy, setActionBusy] = useState<"send" | "approve" | null>(null);

  const refreshApprovals = useCallback(async () => {
    if (!currentId) {
      setApprovalSummary(null);
      return;
    }
    try {
      const res = await getEditApprovals(currentId);
      setApprovalSummary(res);
    } catch {
      setApprovalSummary({
        required_reviewers: [],
        approvals: [],
        can_publish: false,
        pending_reviewer_ids: [],
      });
    }
  }, [currentId]);

  useEffect(() => {
    void refreshApprovals();
  }, [refreshApprovals]);

  async function doSendIssues() {
    if (!current) return;
    setActionBusy("send");
    try {
      const res = await dispatchEditComments(current.id);
      if (res.dispatched === 0) {
        toast.message("No draft comments to send");
      } else {
        toast.success(
          `Sent ${res.dispatched} ${res.dispatched === 1 ? "issue" : "issues"} to the editor`,
        );
      }
      const list = await listEditComments(current.id);
      setComments(list);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : tErr("generic"));
    } finally {
      setActionBusy(null);
    }
  }

  async function doApprove() {
    if (!current) return;
    setActionBusy("approve");
    try {
      await approveEdit(current.id);
      toast.success(tToast("edit_approved"));
      await reload();
      await refreshProject();
      await refreshApprovals();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : tErr("generic"));
    } finally {
      setActionBusy(null);
    }
  }

  async function doRequestChanges() {
    if (!current || !changesNote.trim()) return;
    try {
      const updated = await requestChanges(current.id, changesNote.trim());
      setEdits((prev) => (prev ?? []).map((e) => (e.id === updated.id ? updated : e)));
      toast.success(tToast("edit_changes_requested"));
      setChangesNote("");
      await refreshApprovals();
      await refreshProject();
    } catch {
      toast.error(tErr("generic"));
    }
  }

  const projectFinalised = project.stage_key === "approved_published";

  if (edits === null) {
    return <Skeleton className="h-72 w-full" />;
  }

  return (
    <div className="space-y-4">
      {projectFinalised ? (
        <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-sm">
          <Sparkles className="text-emerald-500 size-4" />
          <span className="font-medium">{t("project_complete_title")}</span>
          <span className="text-muted-foreground text-xs">
            {t("project_complete_hint")}
          </span>
        </div>
      ) : null}
      <RawCutsByShoot projectId={project.id} />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t("cut_versions")}</CardTitle>
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
            <p className="text-muted-foreground text-sm">
              {canUpload ? t("no_edits") : t("no_edits_viewer")}
            </p>
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
              {canRequestChanges &&
                current.status !== "approved" &&
                !projectFinalised && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        <MessageSquareWarning className="mr-2 size-4" />
                        {t("request_changes")}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>
                          {t("request_changes_title")}
                        </AlertDialogTitle>
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
                        <AlertDialogAction
                          onClick={doRequestChanges}
                          disabled={!changesNote.trim()}
                        >
                          {t("request_changes")}
                        </AlertDialogAction>
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
              canComment={!isEditorAssignee && !projectFinalised}
            />
            <EditCommentsList
              comments={comments}
              onUpdate={(c) =>
                setComments((prev) => prev.map((existing) => (existing.id === c.id ? c : existing)))
              }
              onJumpTo={(seconds) => playerRef.current?.seekTo(seconds)}
              canResolve={isEditorAssignee && !projectFinalised}
              currentUserId={currentUserId}
            />
            {!isEditorAssignee ? (
              <div className="space-y-3 border-t pt-3">
                <p className="text-muted-foreground text-xs font-medium uppercase tracking-wider">
                  {t("approvals_title")}
                </p>
                <EditApprovalPanel summary={approvalSummary} />
                {(() => {
                  // Mutually-exclusive reviewer action bar.
                  // Send-issues = "I have feedback"; Approve = "looks
                  // good". A reviewer can't do both on the same cut.
                  const myDraftCount = comments.filter(
                    (c) =>
                      c.author_id === currentUserId && c.sent_at === null,
                  ).length;
                  const myApproval = approvalSummary?.approvals.find(
                    (a) => a.reviewer_id === currentUserId,
                  );
                  const iAmRequired = approvalSummary?.required_reviewers.some(
                    (r) => r.user_id === currentUserId,
                  );
                  const hasDrafts = myDraftCount > 0;
                  const hasApproved = !!myApproval;
                  // Don't render the bar at all if neither button
                  // would be enabled and there's nothing to communicate.
                  if (
                    !iAmRequired ||
                    projectFinalised ||
                    current.status === "approved"
                  ) {
                    return null;
                  }
                  return (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        onClick={doSendIssues}
                        size="sm"
                        variant="outline"
                        disabled={
                          actionBusy !== null || hasApproved || !hasDrafts
                        }
                        title={
                          hasApproved
                            ? "You already approved this cut"
                            : !hasDrafts
                              ? "No draft comments to send"
                              : undefined
                        }
                      >
                        <Send className="size-4" />
                        {actionBusy === "send"
                          ? "Sending…"
                          : hasDrafts
                            ? `Send ${myDraftCount} ${myDraftCount === 1 ? "issue" : "issues"} to editor`
                            : "Send issues to editor"}
                      </Button>
                      <Button
                        onClick={doApprove}
                        size="sm"
                        disabled={
                          actionBusy !== null || hasApproved || hasDrafts
                        }
                        title={
                          hasApproved
                            ? "You already approved this cut"
                            : hasDrafts
                              ? "Send your draft comments first, or delete them"
                              : undefined
                        }
                      >
                        <CheckCircle2 className="size-4" />
                        {actionBusy === "approve"
                          ? "Saving…"
                          : hasApproved
                            ? "Approved"
                            : "Approve this cut"}
                      </Button>
                    </div>
                  );
                })()}
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
