"use client";

import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
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
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { completeShooting } from "@/features/event_scheduling/api";
import { ApiError } from "@/lib/api-client";

interface Props {
  projectId: string;
  onCompleted?: () => void | Promise<void>;
}

/**
 * Director-only CTA that advances the project from `shooting` → `editing`.
 * Dual-check confirmation: opening the dialog is step 1, ticking the
 * acknowledgment checkbox is step 2 — only then is the destructive
 * `Confirm` button enabled. Mirrors the safety-rail pattern used for
 * the project-delete confirm dialog.
 */
export function ShootCompleteButton({ projectId, onCompleted }: Props) {
  const [open, setOpen] = useState(false);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleConfirm() {
    if (!ack || busy) return;
    setBusy(true);
    try {
      await completeShooting(projectId);
      toast.success("Shooting complete — project advanced to Editing");
      setOpen(false);
      setAck(false);
      await onCompleted?.();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to complete shooting",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setAck(false);
      }}
    >
      <AlertDialogTrigger asChild>
        <Button>
          <CheckCircle2 className="size-4" />
          Shoot complete
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Mark all shooting complete?</AlertDialogTitle>
          <AlertDialogDescription>
            This will advance the project to <strong>Editing</strong> and hand
            the raw cuts off to the editor. You won&apos;t be able to schedule
            new shoots from this page after this point — drag the card back
            to <em>Shooting</em> on the board if you really need to.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex items-start gap-3 rounded-md border p-3">
          <Checkbox
            id="ack-shoot-complete"
            checked={ack}
            onCheckedChange={(v) => setAck(v === true)}
            disabled={busy}
            className="mt-0.5"
          />
          <Label
            htmlFor="ack-shoot-complete"
            className="text-sm leading-snug cursor-pointer"
          >
            I confirm every shoot is wrapped and all raw cuts are uploaded.
          </Label>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={!ack || busy}
            onClick={(e) => {
              e.preventDefault();
              void handleConfirm();
            }}
          >
            <CheckCircle2 className="size-4" />
            {busy ? "Completing…" : "Complete shooting"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
