"use client";

import { useTranslations } from "next-intl";
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
import { archiveDepartment } from "@/features/departments/api";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface Props {
  department: { id: string; name: string };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted?: (id: string) => void;
}

export function DeleteDepartmentDialog({
  department,
  open,
  onOpenChange,
  onDeleted,
}: Props) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) setConfirmText("");
  }, [open]);

  const nameMatches = confirmText.trim() === department.name;

  async function onConfirm() {
    if (!nameMatches || submitting) return;
    setSubmitting(true);
    try {
      await archiveDepartment(department.id);
      toast.success(t("deleted_toast", { name: department.name }));
      onOpenChange(false);
      onDeleted?.(department.id);
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : t("delete_failed");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("delete_title")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("delete_subtitle", { name: department.name })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-dept-confirm" className="text-sm">
            {t("delete_confirm_label")}
          </Label>
          <Input
            id="delete-dept-confirm"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder={t("delete_confirm_placeholder")}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            disabled={submitting}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>
            {tCommon("cancel")}
          </AlertDialogCancel>
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
            {submitting ? tCommon("loading") : t("delete_confirm_button")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
