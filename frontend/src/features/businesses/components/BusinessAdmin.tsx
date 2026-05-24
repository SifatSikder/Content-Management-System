"use client";

import { Trash2, UserPlus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
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
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  inviteMember,
  listMemberships,
  revokeMembership,
} from "@/features/businesses/api";
import type { BusinessMembership } from "@/features/businesses/types";
import { ApiError } from "@/lib/api-client";

function StatusBadge({ status }: { status: BusinessMembership["status"] }) {
  const variant: Record<BusinessMembership["status"], "default" | "secondary" | "outline"> = {
    active: "default",
    invited: "secondary",
    revoked: "outline",
  };
  return <Badge variant={variant[status]}>{status}</Badge>;
}

export function BusinessAdmin({ businessId }: { businessId: string }) {
  const t = useTranslations("businesses");
  const tCommon = useTranslations("common");

  const [rows, setRows] = useState<BusinessMembership[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listMemberships(businessId);
      setRows(res.items);
    } catch (exc) {
      toast.error(exc instanceof Error ? exc.message : tCommon("error"));
    } finally {
      setLoading(false);
    }
  }, [businessId, tCommon]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t("members_title")}</h2>
        <InviteDialog businessId={businessId} onInvited={() => void load()} />
      </header>

      {loading ? (
        <Skeleton className="h-32 w-full" />
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("no_members")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("user_id")}</TableHead>
              <TableHead>{t("status")}</TableHead>
              <TableHead>{t("joined_at")}</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-mono text-xs">{m.user_id}</TableCell>
                <TableCell>
                  <StatusBadge status={m.status} />
                </TableCell>
                <TableCell>
                  {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "—"}
                </TableCell>
                <TableCell>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <Trash2 className="size-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t("revoke_title")}</AlertDialogTitle>
                        <AlertDialogDescription>
                          {t("revoke_confirm")}
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={async () => {
                            try {
                              await revokeMembership(businessId, m.id);
                              toast.success(t("revoked_toast"));
                              await load();
                            } catch (exc) {
                              toast.error(
                                exc instanceof Error ? exc.message : tCommon("error"),
                              );
                            }
                          }}
                        >
                          {t("revoke_action")}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}

function InviteDialog({
  businessId,
  onInvited,
}: {
  businessId: string;
  onInvited: () => void;
}) {
  const t = useTranslations("businesses");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await inviteMember(businessId, { email: email.trim() });
      toast.success(t("invited_toast"));
      setOpen(false);
      setEmail("");
      onInvited();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : t("invite_failed");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <UserPlus className="mr-2 size-4" />
          {t("invite_action")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("invite_title")}</DialogTitle>
          <DialogDescription>{t("invite_subtitle")}</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2">
            <Label htmlFor="invite-email">{t("email_label")}</Label>
            <Input
              id="invite-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="member@company.com"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? tCommon("loading") : t("invite_action")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
