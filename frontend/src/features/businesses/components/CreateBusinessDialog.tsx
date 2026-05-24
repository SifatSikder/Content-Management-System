"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useState } from "react";
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
  DialogTrigger,
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
import { createBusiness } from "@/features/businesses/api";
import type { Business } from "@/features/businesses/types";
import { ApiError } from "@/lib/api-client";

const schema = z.object({
  name: z.string().min(1).max(200),
  slug: z
    .string()
    .min(1)
    .max(120)
    .regex(/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/, "lowercase, digits, hyphens")
    .optional()
    .or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export function CreateBusinessDialog({
  trigger,
  onCreated,
}: {
  trigger: React.ReactNode;
  onCreated?: (b: Business) => void;
}) {
  const t = useTranslations("businesses");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", slug: "" },
  });

  async function onSubmit(values: FormValues) {
    setSubmitting(true);
    try {
      const slug = values.slug?.trim() || undefined;
      const business = await createBusiness({ name: values.name.trim(), slug });
      toast.success(t("created_toast", { name: business.name }));
      setOpen(false);
      form.reset();
      onCreated?.(business);
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : t("create_failed");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("create_title")}</DialogTitle>
          <DialogDescription>{t("create_subtitle")}</DialogDescription>
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
            <FormField
              control={form.control}
              name="slug"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("slug_label")}</FormLabel>
                  <FormControl>
                    <Input placeholder="acme-co" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
              >
                {tCommon("cancel")}
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? tCommon("loading") : t("create_action")}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
