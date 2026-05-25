"use client";

import { Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  createCast,
  deleteCast,
  listCast,
} from "@/features/participant_roster/api";
import type { CastMember } from "@/features/participant_roster/types";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

interface Props {
  project: Project;
}

/**
 * Lead form variant of the participant-roster tab.
 *
 * Shares the `participants` table + `/cast` routes with `CastingTab`, but
 * renders only the lead-relevant fields: display name, email, phone,
 * source, notes. No release-form upload, no confirm toggle.
 *
 * Created rows are tagged `kind="lead"` on the server so the cast tab and
 * the lead tab never mix entries even if a department somehow ends up with
 * both modes.
 */
export function LeadsTab({ project }: Props) {
  const t = useTranslations("leads");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");

  const [leads, setLeads] = useState<CastMember[] | null>(null);
  const [draft, setDraft] = useState({
    name: "",
    contact_email: "",
    contact_phone: "",
    source: "",
    notes: "",
  });
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const all = await listCast(project.id);
      // The participants table holds both cast and lead rows for any
      // department that ever enabled both modes. Filter client-side so
      // we never show cast rows here.
      setLeads(all.filter((p) => p.kind === "lead"));
    } catch {
      toast.error(tErr("generic"));
    }
  }, [project.id, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await createCast(project.id, {
        kind: "lead",
        name: draft.name.trim(),
        contact_email: draft.contact_email.trim() || null,
        contact_phone: draft.contact_phone.trim() || null,
        source: draft.source.trim() || null,
        notes: draft.notes.trim() || null,
      });
      setDraft({ name: "", contact_email: "", contact_phone: "", source: "", notes: "" });
      await reload();
      toast.success(t("created_toast"));
    } catch (exc) {
      toast.error(exc instanceof ApiError ? exc.message : tErr("generic"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(lead: CastMember) {
    try {
      await deleteCast(lead.id);
      await reload();
      toast.success(t("deleted_toast"));
    } catch (exc) {
      toast.error(exc instanceof ApiError ? exc.message : tErr("generic"));
    }
  }

  return (
    <div className="space-y-6">
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">{t("new_lead_title")}</h3>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="lead-name">{t("display_name")}</Label>
              <Input
                id="lead-name"
                required
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="lead-email">{t("email")}</Label>
              <Input
                id="lead-email"
                type="email"
                value={draft.contact_email}
                onChange={(e) => setDraft({ ...draft, contact_email: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="lead-phone">{t("phone")}</Label>
              <Input
                id="lead-phone"
                value={draft.contact_phone}
                onChange={(e) => setDraft({ ...draft, contact_phone: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="lead-source">{t("source")}</Label>
              <Input
                id="lead-source"
                placeholder={t("source_placeholder")}
                value={draft.source}
                onChange={(e) => setDraft({ ...draft, source: e.target.value })}
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="lead-notes">{t("notes")}</Label>
            <Textarea
              id="lead-notes"
              rows={3}
              value={draft.notes}
              onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
            />
          </div>
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={busy || !draft.name.trim()}>
              {t("add_lead")}
            </Button>
          </div>
        </form>
      </Card>

      <div className="space-y-2">
        {leads === null && (
          <p className="text-muted-foreground text-sm">{tCommon("loading")}</p>
        )}
        {leads !== null && leads.length === 0 && (
          <p className="text-muted-foreground text-sm">{t("empty")}</p>
        )}
        {leads?.map((lead) => (
          <Card key={lead.id} className="flex items-start justify-between gap-3 p-3">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="font-medium">{lead.name}</div>
              <div className="text-muted-foreground space-x-3 text-xs">
                {lead.contact_email && <span>{lead.contact_email}</span>}
                {lead.contact_phone && <span>{lead.contact_phone}</span>}
                {lead.source && <span>· {lead.source}</span>}
              </div>
              {lead.notes && (
                <p className="text-muted-foreground whitespace-pre-line text-sm">
                  {lead.notes}
                </p>
              )}
            </div>
            <ConfirmDialog
              title={t("confirm_delete_title")}
              description={t("confirm_delete_body")}
              confirmLabel={tCommon("delete")}
              onConfirm={() => void handleDelete(lead)}
            >
              <Button variant="ghost" size="icon" aria-label={tCommon("delete")}>
                <Trash2 className="size-4" />
              </Button>
            </ConfirmDialog>
          </Card>
        ))}
      </div>
    </div>
  );
}
