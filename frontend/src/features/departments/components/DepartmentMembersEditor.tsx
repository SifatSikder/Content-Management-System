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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  inviteDepartmentMember,
  listDepartmentMembers,
  listRoles,
  removeDepartmentMember,
} from "@/features/departments/api";
import type {
  DepartmentMembership,
  DepartmentRole,
} from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function roleLabel(role: DepartmentRole): string {
  return role.name_i18n.en ?? role.name_i18n.nl ?? role.key;
}

/**
 * Department-scoped member management.
 *
 * Members live here, not at the business level — adding someone to a
 * department is what grants them access (the matching business membership
 * is auto-created by `assign_department_member`, and auto-revoked when
 * their last department membership in the business goes away).
 *
 * Invites flow through the Next.js BFF route at
 * `/api/departments/[id]/invite`, which find-or-creates the platform user
 * + sends the welcome email + writes the membership in one round trip.
 */
export function DepartmentMembersEditor({ departmentId }: { departmentId: string }) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [members, setMembers] = useState<DepartmentMembership[]>([]);
  const [roles, setRoles] = useState<DepartmentRole[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [mems, rs] = await Promise.all([
        listDepartmentMembers(departmentId),
        listRoles(departmentId),
      ]);
      setMembers(mems.items);
      setRoles(rs.items);
    } catch (exc) {
      toast.error(exc instanceof Error ? exc.message : tCommon("error"));
    } finally {
      setLoading(false);
    }
  }, [departmentId, tCommon]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>{t("members_title")}</CardTitle>
          <CardDescription>{t("members_subtitle")}</CardDescription>
        </div>
        <InviteMemberDialog
          departmentId={departmentId}
          roles={roles}
          onInvited={() => void load()}
        />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : members.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("members_empty")}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("member")}</TableHead>
                <TableHead>{t("role")}</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((m) => {
                const isCeo = m.user.role === "ceo";
                return (
                  <TableRow key={m.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="size-8">
                          {m.user.avatar_url ? (
                            <AvatarImage src={m.user.avatar_url} alt={m.user.name} />
                          ) : null}
                          <AvatarFallback>{initials(m.user.name)}</AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">
                            {m.user.name}
                          </div>
                          <div className="text-muted-foreground truncate text-xs">
                            {m.user.email}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{roleLabel(m.role)}</Badge>
                    </TableCell>
                    <TableCell>
                      {isCeo ? null : (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <Trash2 className="size-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                {t("remove_member_title")}
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                {t("remove_member_confirm", { name: m.user.name })}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={async () => {
                                  try {
                                    await removeDepartmentMember(departmentId, m.id);
                                    toast.success(t("member_removed_toast"));
                                    await load();
                                  } catch (exc) {
                                    const msg =
                                      exc instanceof ApiError
                                        ? exc.message
                                        : tCommon("error");
                                    toast.error(msg);
                                  }
                                }}
                              >
                                {t("remove_member_action")}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function InviteMemberDialog({
  departmentId,
  roles,
  onInvited,
}: {
  departmentId: string;
  roles: DepartmentRole[];
  onInvited: () => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [roleId, setRoleId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const canInvite = roles.length > 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!roleId) return;
    setSubmitting(true);
    try {
      const result = await inviteDepartmentMember(departmentId, {
        email: email.trim(),
        name: name.trim(),
        role_id: roleId,
      });
      if (result.invite_url_for_admin) {
        // Gmail not configured — show the link so the admin can hand it over.
        toast.success(t("invited_toast_with_link"), {
          description: result.invite_url_for_admin,
          duration: 30_000,
        });
      } else {
        toast.success(t("invited_toast"));
      }
      setOpen(false);
      setEmail("");
      setName("");
      setRoleId("");
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
        <Button size="sm" disabled={!canInvite}>
          <UserPlus className="mr-2 size-4" />
          {t("invite_member_action")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("invite_member_title")}</DialogTitle>
          <DialogDescription>{t("invite_member_subtitle")}</DialogDescription>
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
          <div className="space-y-2">
            <Label htmlFor="invite-name">{t("name_label")}</Label>
            <Input
              id="invite-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
            />
          </div>
          <div className="space-y-2">
            <Label>{t("role_label")}</Label>
            <Select value={roleId} onValueChange={setRoleId}>
              <SelectTrigger>
                <SelectValue placeholder={t("role_placeholder")} />
              </SelectTrigger>
              <SelectContent>
                {roles.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {roleLabel(r)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={submitting || !roleId}>
              {submitting ? tCommon("loading") : t("invite_member_action")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
