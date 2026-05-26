"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Trash2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  createLogoUploadSession,
  finaliseLogoUpload,
  removeBusinessLogo,
  updateBusiness,
} from "@/features/businesses/api";
import { BusinessLogo } from "@/features/businesses/components/BusinessLogo";
import type { Business } from "@/features/businesses/types";
import { performResumableUpload } from "@/features/asset_review_with_timecodes/lib/resumable-upload";
import { ApiError } from "@/lib/api-client";

const ALLOWED_MIME = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
]);
const MAX_BYTES = 2 * 1024 * 1024;

const schema = z.object({
  name: z.string().min(1).max(200),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  business: { id: string; name: string; logo_url: string | null };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (b: Business) => void;
}

export function EditBusinessDialog({
  business,
  open,
  onOpenChange,
  onSaved,
}: Props) {
  const t = useTranslations("businesses");
  const tCommon = useTranslations("common");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const [removeMarked, setRemoveMarked] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: business.name },
  });

  // Reset every time the dialog opens against a (possibly different) business.
  useEffect(() => {
    if (open) {
      form.reset({ name: business.name });
      setPendingFile(null);
      setPendingPreview(null);
      setRemoveMarked(false);
    }
  }, [open, business.id, business.name, form]);

  // Object URLs hold a reference until revoked — drop them when the
  // selection changes or the dialog closes.
  useEffect(() => {
    if (!pendingPreview) return;
    return () => URL.revokeObjectURL(pendingPreview);
  }, [pendingPreview]);

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file) return;
    if (!ALLOWED_MIME.has(file.type)) {
      toast.error(t("logo_invalid_type"));
      return;
    }
    if (file.size > MAX_BYTES) {
      toast.error(t("logo_too_large"));
      return;
    }
    setPendingFile(file);
    setPendingPreview(URL.createObjectURL(file));
    setRemoveMarked(false);
  }

  async function onSubmit(values: FormValues) {
    const nextName = values.name.trim();
    const nameChanged = nextName !== business.name;
    const hasLogoWork = pendingFile !== null || removeMarked;
    if (!nameChanged && !hasLogoWork) {
      onOpenChange(false);
      return;
    }
    setSubmitting(true);
    try {
      let latest: Business | null = null;

      if (nameChanged) {
        latest = await updateBusiness(business.id, { name: nextName });
      }

      if (pendingFile) {
        const init = await createLogoUploadSession(business.id, {
          content_type: pendingFile.type,
          size_bytes: pendingFile.size,
        });
        await performResumableUpload({
          sessionUrl: init.upload_session_url,
          file: pendingFile,
        });
        latest = await finaliseLogoUpload(business.id, {
          gcs_object_name: init.gcs_object_name,
        });
      } else if (removeMarked && business.logo_url) {
        latest = await removeBusinessLogo(business.id);
      }

      toast.success(t("saved_toast", { name: latest?.name ?? nextName }));
      onOpenChange(false);
      if (latest) onSaved?.(latest);
    } catch (exc) {
      const fallback =
        pendingFile !== null ? t("logo_upload_failed") : t("edit_failed");
      const msg = exc instanceof ApiError ? exc.message : fallback;
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  const showCurrentLogo = business.logo_url && !removeMarked && !pendingPreview;
  const previewUrl = pendingPreview ?? (showCurrentLogo ? business.logo_url : null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("edit_title")}</DialogTitle>
          <DialogDescription>{t("edit_subtitle")}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <div className="space-y-2">
              <FormLabel>{t("logo_label")}</FormLabel>
              <div className="flex items-center gap-4">
                <BusinessLogo
                  logoUrl={previewUrl}
                  name={business.name}
                  size={56}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={onPickFile}
                    className="sr-only"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={submitting}
                  >
                    <Upload className="mr-2 size-4" />
                    {previewUrl ? t("logo_replace") : t("logo_upload")}
                  </Button>
                  {previewUrl ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setPendingFile(null);
                        setPendingPreview(null);
                        if (business.logo_url) setRemoveMarked(true);
                      }}
                      disabled={submitting}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="mr-2 size-4" />
                      {t("logo_remove")}
                    </Button>
                  ) : null}
                </div>
              </div>
              <p className="text-muted-foreground text-xs">{t("logo_hint")}</p>
            </div>

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("name_label")}</FormLabel>
                  <FormControl>
                    <Input
                      placeholder={t("name_placeholder")}
                      autoFocus
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => onOpenChange(false)}
                disabled={submitting}
              >
                {tCommon("cancel")}
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? tCommon("loading") : t("edit_save")}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
