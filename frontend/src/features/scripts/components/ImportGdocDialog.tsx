"use client";

import { Cloud, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

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
import { importGdoc } from "@/features/drive/api";
import type { ScriptVersion } from "@/features/scripts/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  projectId: string;
  onImported: (version: ScriptVersion) => void;
  trigger?: React.ReactNode;
  disabled?: boolean;
}

export function ImportGdocDialog({ projectId, onImported, trigger, disabled }: Props) {
  const t = useTranslations("script");
  const tDrive = useTranslations("drive");
  const tErr = useTranslations("errors");
  const [open, setOpen] = useState(false);
  const [document, setDocument] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!document.trim()) return;
    setBusy(true);
    try {
      const version = (await importGdoc(projectId, { document })) as ScriptVersion;
      onImported(version);
      toast.success(t("import_succeeded"));
      setOpen(false);
      setDocument("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 412) {
        toast.error(tDrive("disconnected"));
      } else if (err instanceof ApiError && err.status === 403) {
        toast.error(t("import_forbidden"));
      } else if (err instanceof ApiError && err.status === 404) {
        toast.error(t("import_not_found"));
      } else if (err instanceof ApiError && err.status === 400) {
        toast.error(t("import_invalid_url"));
      } else {
        toast.error(tErr("generic"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button size="sm" variant="outline" disabled={disabled}>
            <Cloud className="mr-2 size-4" />
            {t("import_from_drive")}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("import_dialog_title")}</DialogTitle>
          <DialogDescription>{t("import_dialog_description")}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="gdoc-input">{t("import_dialog_field_label")}</Label>
            <Input
              id="gdoc-input"
              placeholder="https://docs.google.com/document/d/…"
              value={document}
              onChange={(e) => setDocument(e.target.value)}
              autoComplete="off"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={busy || !document.trim()}>
              {busy ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
              {t("import_submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
