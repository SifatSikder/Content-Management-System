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
import { deleteBusiness } from "@/features/businesses/api";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface Props {
  business: { id: string; name: string };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted?: (id: string) => void;
}

export function DeleteBusinessDialog({
  business,
  open,
  onOpenChange,
  onDeleted,
}: Props) {
  const t = useTranslations("businesses");
  const tCommon = useTranslations("common");
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) setConfirmText("");
  }, [open]);

  const nameMatches = confirmText.trim() === business.name;

  async function onConfirm() {
    if (!nameMatches || submitting) return;
    setSubmitting(true);
    try {
      await deleteBusiness(business.id);
      toast.success(t("deleted_toast", { name: business.name }));
      onOpenChange(false);
      onDeleted?.(business.id);
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
            {t("delete_subtitle", { name: business.name })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <Label htmlFor="delete-business-confirm" className="text-sm">
            {t("delete_confirm_label")}
          </Label>
          <Input
            id="delete-business-confirm"
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
