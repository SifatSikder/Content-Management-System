"use client";

import { FolderKanban, Plus } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { createDepartment } from "@/features/departments/api";
import { useDepartments } from "@/features/departments/hooks/useDepartments";
import { ApiError } from "@/lib/api-client";

export function DepartmentList({
  businessId,
  businessSlug,
  canEdit,
}: {
  businessId: string;
  businessSlug: string;
  canEdit: boolean;
}) {
  const t = useTranslations("departments");
  const { status, items, reload } = useDepartments(businessId);

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t("list_title")}</h2>
        {canEdit ? (
          <CreateDepartmentDialog businessId={businessId} onCreated={() => void reload()} />
        ) : null}
      </header>

      {status === "loading" ? (
        <div className="grid gap-3 md:grid-cols-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("empty")}</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((d) => (
            <Card key={d.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <FolderKanban className="size-4" />
                      <span className="truncate">{d.name}</span>
                    </CardTitle>
                    <CardDescription className="font-mono text-xs">
                      {d.slug}
                    </CardDescription>
                  </div>
                  {d.archived_at ? (
                    <Badge variant="outline">{t("archived")}</Badge>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-muted-foreground text-xs">
                  {d.capabilities.length === 0
                    ? t("no_capabilities")
                    : t("capabilities_count", { count: d.capabilities.length })}
                </div>
                <Button asChild size="sm" variant="outline">
                  <Link href={`/businesses/${businessSlug}/departments/${d.id}`}>
                    {t("open")}
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

function CreateDepartmentDialog({
  businessId,
  onCreated,
}: {
  businessId: string;
  onCreated: () => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createDepartment(businessId, { name: name.trim() });
      toast.success(t("created_toast"));
      setOpen(false);
      setName("");
      onCreated();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : t("create_failed");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 size-4" />
          {t("create_action")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("create_title")}</DialogTitle>
          <DialogDescription>{t("create_subtitle")}</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2">
            <Label htmlFor="dept-name">{t("name_label")}</Label>
            <Input
              id="dept-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? tCommon("loading") : t("create_action")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
