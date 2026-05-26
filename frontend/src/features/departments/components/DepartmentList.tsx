"use client";

import { FolderKanban, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { createDepartment } from "@/features/departments/api";
import { DeleteDepartmentDialog } from "@/features/departments/components/DeleteDepartmentDialog";
import { RenameDepartmentDialog } from "@/features/departments/components/RenameDepartmentDialog";
import { useDepartments } from "@/features/departments/hooks/useDepartments";
import type { Department } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

type DialogState =
  | { kind: "none" }
  | { kind: "edit"; department: Department }
  | { kind: "delete"; department: Department };

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
  const [dialog, setDialog] = useState<DialogState>({ kind: "none" });

  function closeDialog() {
    setDialog({ kind: "none" });
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t("list_title")}</h2>
        {canEdit ? (
          <CreateDepartmentDialog businessId={businessId} onCreated={() => void reload()} />
        ) : null}
      </header>

      {status === "loading" ? (
        <div className="space-y-2">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("empty")}</p>
      ) : (
        <ul className="divide-border bg-card divide-y rounded-xl border">
          {items.map((d) => (
            <li
              key={d.id}
              className="hover:bg-accent/40 group flex items-center gap-3 px-4 py-3 transition-colors"
            >
              <FolderKanban className="text-muted-foreground size-4 shrink-0" />
              <Link
                href={`/businesses/${businessSlug}/departments/${d.id}`}
                aria-label={t("row_open_aria", { name: d.name })}
                className="focus-visible:ring-ring -mx-1 flex min-w-0 flex-1 items-center gap-2 truncate rounded px-1 text-sm font-medium focus-visible:ring-2 focus-visible:outline-none"
              >
                <span className="truncate">{d.name}</span>
                {d.archived_at ? (
                  <Badge variant="outline">{t("archived")}</Badge>
                ) : null}
              </Link>
              {canEdit ? (
                <TooltipProvider delayDuration={150}>
                  <div className="flex shrink-0 items-center gap-0.5">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t("edit_action")}
                          onClick={() =>
                            setDialog({ kind: "edit", department: d })
                          }
                          className="size-8"
                        >
                          <Pencil className="size-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{t("edit_action")}</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t("delete_action")}
                          onClick={() =>
                            setDialog({ kind: "delete", department: d })
                          }
                          className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 size-8"
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{t("delete_action")}</TooltipContent>
                    </Tooltip>
                  </div>
                </TooltipProvider>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {dialog.kind === "edit" ? (
        <RenameDepartmentDialog
          department={{ id: dialog.department.id, name: dialog.department.name }}
          open
          onOpenChange={(o) => (o ? null : closeDialog())}
          onRenamed={() => void reload()}
        />
      ) : null}
      {dialog.kind === "delete" ? (
        <DeleteDepartmentDialog
          department={{ id: dialog.department.id, name: dialog.department.name }}
          open
          onOpenChange={(o) => (o ? null : closeDialog())}
          onDeleted={() => void reload()}
        />
      ) : null}
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
