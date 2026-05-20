"use client";

import { Send, Trash2 } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { listTeam, removeMember, resendInvite } from "@/features/team/api";
import { InviteDialog } from "@/features/team/components/InviteDialog";
import type { TeamMember } from "@/features/team/types";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString();
}

export default function TeamPage() {
  const tAuth = useTranslations("auth");
  const tCommon = useTranslations("common");
  const tRoles = useTranslations("roles");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const auth = useAuth();
  const [members, setMembers] = useState<TeamMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const resp = await listTeam();
      setMembers(resp.items);
    } catch {
      setError(tErr("generic"));
    }
  }, [tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (!auth.user) return null;
  if (auth.user.role !== "ceo") {
    return (
      <div className="p-6 text-muted-foreground text-sm">{tErr("unauthorized")}</div>
    );
  }

  async function onResend(member: TeamMember) {
    try {
      const resp = await resendInvite(member.id);
      if (resp.invite_url_for_admin) {
        await navigator.clipboard.writeText(resp.invite_url_for_admin).catch(() => undefined);
        toast.success(`${tToast("invite_resent")} (URL copied to clipboard)`);
      } else {
        toast.success(tToast("invite_resent"));
      }
      void reload();
    } catch {
      toast.error(tErr("generic"));
    }
  }

  async function onRemove(member: TeamMember) {
    try {
      await removeMember(member.id);
      toast.success(tToast("member_removed"));
      void reload();
    } catch {
      toast.error(tErr("generic"));
    }
  }

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{tAuth("team_title")}</h1>
          <p className="text-muted-foreground text-sm">{tAuth("team_subtitle")}</p>
        </div>
        <InviteDialog onInvited={() => void reload()} />
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
          {error}
          <Button variant="link" onClick={() => void reload()} className="ml-2 h-auto p-0">
            {tCommon("retry")}
          </Button>
        </div>
      )}

      {members === null ? (
        <Skeleton className="h-48 w-full" />
      ) : members.length === 0 ? (
        <p className="text-muted-foreground text-sm">{tCommon("empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{tAuth("invitee_name_label")}</TableHead>
                <TableHead>{tAuth("email_label")}</TableHead>
                <TableHead>{tAuth("role_label")}</TableHead>
                <TableHead>{tAuth("status_label")}</TableHead>
                <TableHead>{tAuth("last_login_label")}</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="font-medium">{m.name}</TableCell>
                  <TableCell className="text-muted-foreground">{m.email}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{tRoles(m.role)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={m.status === "active" ? "secondary" : "outline"}>
                      {m.status === "active" ? tAuth("status_active") : tAuth("status_pending")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">
                    {formatDate(m.last_login_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      {m.status === "pending" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={tAuth("resend_invite")}
                          onClick={() => void onResend(m)}
                        >
                          <Send className="size-4" />
                        </Button>
                      )}
                      {m.id !== auth.user!.id && (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={tAuth("remove_member")}
                            >
                              <Trash2 className="text-destructive size-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                {tAuth("remove_member")}
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                {tAuth("remove_member_confirm")} {m.email}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                              <AlertDialogAction onClick={() => void onRemove(m)}>
                                {tCommon("delete")}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
