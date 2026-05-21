"use client";

import { useState } from "react";

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

/**
 * Reusable yes/no confirmation modal. Wraps shadcn AlertDialog so callers
 * don't repeat the boilerplate. Pass an inline trigger (typically a Button
 * or IconButton) as children and the destructive action in `onConfirm`.
 *
 *     <ConfirmDialog
 *       title="Delete this photo?"
 *       description="This cannot be undone."
 *       confirmLabel="Delete"
 *       onConfirm={() => deletePhoto(id)}
 *     >
 *       <Button variant="ghost" size="icon"><Trash2 /></Button>
 *     </ConfirmDialog>
 */
interface Props {
  title: string;
  description?: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void | Promise<void>;
  children: React.ReactNode;
}

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  cancelLabel,
  destructive = true,
  onConfirm,
  children,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {/* Radix's AlertDialog requires a Description in the tree. When the
              caller didn't supply one, we render a visually-hidden description
              that echoes the title — screen readers still get meaningful
              context, and Radix's accessibility check stops warning. */}
          <AlertDialogDescription className={description ? undefined : "sr-only"}>
            {description ?? title}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelLabel ?? "Cancel"}</AlertDialogCancel>
          <AlertDialogAction
            variant={destructive ? "destructive" : "default"}
            onClick={async () => {
              await onConfirm();
              setOpen(false);
            }}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
