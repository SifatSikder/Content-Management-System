"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
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
import { updateBusiness } from "@/features/businesses/api";
import type { Business } from "@/features/businesses/types";
import { ApiError } from "@/lib/api-client";

const schema = z.object({
  name: z.string().min(1).max(200),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  business: { id: string; name: string };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRenamed?: (b: Business) => void;
}

export function RenameBusinessDialog({
  business,
  open,
  onOpenChange,
  onRenamed,
}: Props) {
  const t = useTranslations("businesses");
  const tCommon = useTranslations("common");
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: business.name },
  });

  // Reset the form to the current business name each time the dialog opens
  // so it never starts with stale values from the previous target row.
  useEffect(() => {
    if (open) {
      form.reset({ name: business.name });
    }
  }, [open, business.name, form]);

  async function onSubmit(values: FormValues) {
    const next = values.name.trim();
    if (next === business.name) {
      onOpenChange(false);
      return;
    }
    setSubmitting(true);
    try {
      const updated = await updateBusiness(business.id, { name: next });
      toast.success(t("renamed_toast", { name: updated.name }));
      onOpenChange(false);
      onRenamed?.(updated);
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : t("rename_failed");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("rename_title")}</DialogTitle>
          <DialogDescription>{t("rename_subtitle")}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
                {submitting ? tCommon("loading") : t("rename_save")}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
