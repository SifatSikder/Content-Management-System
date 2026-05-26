"use client";

import { Building2, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { CreateBusinessDialog } from "@/features/businesses/components/CreateBusinessDialog";
import { DeleteBusinessDialog } from "@/features/businesses/components/DeleteBusinessDialog";
import { RenameBusinessDialog } from "@/features/businesses/components/RenameBusinessDialog";
import { useBusinesses } from "@/features/businesses/hooks/useBusinesses";
import type { MeBusinessEntry } from "@/features/businesses/types";

type DialogState =
  | { kind: "none" }
  | { kind: "rename"; business: MeBusinessEntry }
  | { kind: "delete"; business: MeBusinessEntry };

export default function BusinessesPage() {
  const t = useTranslations("businesses");
  const auth = useAuth();
  const { status, items, reload } = useBusinesses();
  const canManage = auth.user?.is_super_admin ?? false;
  const [dialog, setDialog] = useState<DialogState>({ kind: "none" });

  function closeDialog() {
    setDialog({ kind: "none" });
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("page_title")}</h1>
          <p className="text-muted-foreground text-sm">{t("page_subtitle")}</p>
        </div>
        {canManage ? (
          <CreateBusinessDialog
            trigger={
              <Button>
                <Plus className="mr-2 size-4" />
                {t("create_action")}
              </Button>
            }
            onCreated={() => void reload()}
          />
        ) : null}
      </header>

      {status === "loading" ? (
        <div className="space-y-2">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("none")}</CardTitle>
            <CardDescription>{t("none_subtitle")}</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <ul className="divide-border bg-card divide-y rounded-xl border">
          {items.map((b) => (
            <li
              key={b.id}
              className="hover:bg-accent/40 group flex items-center gap-3 px-4 py-3 transition-colors"
            >
              <Building2 className="text-muted-foreground size-4 shrink-0" />
              <Link
                href={`/businesses/${b.slug}`}
                aria-label={t("row_open_aria", { name: b.name })}
                className="focus-visible:ring-ring -mx-1 min-w-0 flex-1 truncate rounded px-1 text-sm font-medium focus-visible:ring-2 focus-visible:outline-none"
              >
                {b.name}
              </Link>
              {canManage ? (
                <TooltipProvider delayDuration={150}>
                  <div className="flex shrink-0 items-center gap-0.5">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t("rename_action")}
                          onClick={() =>
                            setDialog({ kind: "rename", business: b })
                          }
                          className="size-8"
                        >
                          <Pencil className="size-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{t("rename_action")}</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t("delete_action")}
                          onClick={() =>
                            setDialog({ kind: "delete", business: b })
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

      {dialog.kind === "rename" ? (
        <RenameBusinessDialog
          business={{ id: dialog.business.id, name: dialog.business.name }}
          open
          onOpenChange={(o) => (o ? null : closeDialog())}
          onRenamed={() => void reload()}
        />
      ) : null}
      {dialog.kind === "delete" ? (
        <DeleteBusinessDialog
          business={{ id: dialog.business.id, name: dialog.business.name }}
          open
          onOpenChange={(o) => (o ? null : closeDialog())}
          onDeleted={() => void reload()}
        />
      ) : null}
    </div>
  );
}
