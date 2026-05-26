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
import { updateDepartment } from "@/features/departments/api";
import type { Department } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

const schema = z.object({
  name: z.string().min(1).max(200),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  department: { id: string; name: string };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRenamed?: (d: Department) => void;
}

export function RenameDepartmentDialog({
  department,
  open,
  onOpenChange,
  onRenamed,
}: Props) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: department.name },
  });

  useEffect(() => {
    if (open) form.reset({ name: department.name });
  }, [open, department.name, form]);

  async function onSubmit(values: FormValues) {
    const next = values.name.trim();
    if (next === department.name) {
      onOpenChange(false);
      return;
    }
    setSubmitting(true);
    try {
      const updated = await updateDepartment(department.id, { name: next });
      toast.success(t("renamed_toast", { name: updated.name }));
      onOpenChange(false);
      onRenamed?.(updated);
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : t("edit_failed");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("edit_title")}</DialogTitle>
          <DialogDescription>{t("edit_subtitle")}</DialogDescription>
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
                    <Input autoFocus {...field} />
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
