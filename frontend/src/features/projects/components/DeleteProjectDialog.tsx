"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { deleteProject } from "@/features/projects/api";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface Props {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Optional — caller can intercept post-delete (e.g. close a side panel).
   *  Default: navigate back to /projects. */
  onDeleted?: () => void;
}

export function DeleteProjectDialog({
  project,
  open,
  onOpenChange,
  onDeleted,
}: Props) {
  const router = useRouter();
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) setConfirmText("");
  }, [open]);

  const nameMatches = confirmText.trim() === project.title;

  async function onConfirm() {
    if (!nameMatches || submitting) return;
    setSubmitting(true);
    try {
      await deleteProject(project.id);
      toast.success(`"${project.title}" deleted`);
      onOpenChange(false);
      if (onDeleted) {
        onDeleted();
      } else {
        router.push("/projects");
      }
    } catch (exc) {
      const msg =
        exc instanceof ApiError ? exc.message : "Failed to delete project";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete project</AlertDialogTitle>
          <AlertDialogDescription>
            Soft-deletes &ldquo;{project.title}&rdquo;. Recoverable for 30 days
            via the projects list filter. Type the project name to confirm.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-project-confirm" className="text-sm">
            Type <strong>{project.title}</strong> to confirm
          </Label>
          <Input
            id="delete-project-confirm"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={project.title}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            disabled={submitting}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={!nameMatches || submitting}
            onClick={(e) => {
              e.preventDefault();
              void onConfirm();
            }}
            className={cn(
              "bg-destructive text-destructive-foreground",
              "hover:bg-destructive/90 focus-visible:ring-destructive/30",
            )}
          >
            {submitting ? "Deleting…" : "Delete project"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
