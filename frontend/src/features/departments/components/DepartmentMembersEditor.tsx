"use client";

import { MoreHorizontal, UserPlus } from "lucide-react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { setBusinessMembershipStatus } from "@/features/businesses/api";
import {
  changeDepartmentMemberRole,
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
  // Track which member's row-level dialog is currently open. Only one
  // change-role / remove-confirm dialog can be open at a time, and the
  // DropdownMenu closes before its child Dialog mounts (Radix focus
  // management), so we hold the target in component state.
  const [roleDialogFor, setRoleDialogFor] = useState<DepartmentMembership | null>(
    null,
  );
  const [removeDialogFor, setRemoveDialogFor] = useState<DepartmentMembership | null>(
    null,
  );

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

  async function removeMember(m: DepartmentMembership) {
    try {
      await removeDepartmentMember(departmentId, m.id);
      toast.success(t("member_removed_toast"));
      await load();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    }
  }

  async function setStatus(
    m: DepartmentMembership,
    status: "active" | "revoked",
  ) {
    if (!m.business_membership_id) {
      toast.error(tCommon("error"));
      return;
    }
    try {
      await setBusinessMembershipStatus(m.business_id, m.business_membership_id, status);
      toast.success(
        status === "active"
          ? t("member_activated_toast")
          : t("member_deactivated_toast"),
      );
      await load();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    }
  }

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
                <TableHead>{t("status")}</TableHead>
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
                      {m.user.is_pending ? (
                        <Badge variant="secondary">{t("status_pending")}</Badge>
                      ) : m.business_membership_status === "revoked" ? (
                        <Badge variant="outline">{t("status_inactive")}</Badge>
                      ) : (
                        <Badge>{t("status_active")}</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {isCeo ? null : (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={t("member_actions")}
                            >
                              <MoreHorizontal className="size-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onSelect={() => setRoleDialogFor(m)}
                            >
                              {t("change_role")}
                            </DropdownMenuItem>
                            {/* Soft enable/disable only for accepted users
                                (a Pending user is in a pre-accept state, no
                                point flipping their business membership). */}
                            {!m.user.is_pending ? (
                              m.business_membership_status === "revoked" ? (
                                <DropdownMenuItem
                                  onSelect={() => void setStatus(m, "active")}
                                >
                                  {t("make_active")}
                                </DropdownMenuItem>
                              ) : (
                                <DropdownMenuItem
                                  onSelect={() => void setStatus(m, "revoked")}
                                >
                                  {t("make_inactive")}
                                </DropdownMenuItem>
                              )
                            ) : null}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              variant="destructive"
                              onSelect={() => setRemoveDialogFor(m)}
                            >
                              {m.user.is_pending
                                ? t("cancel_invitation_action")
                                : t("remove_member_action")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}

        {/* Change role dialog — driven by `roleDialogFor` state. */}
        <ChangeRoleDialog
          membership={roleDialogFor}
          roles={roles}
          departmentId={departmentId}
          onClose={() => setRoleDialogFor(null)}
          onChanged={() => {
            setRoleDialogFor(null);
            void load();
          }}
        />

        {/* Remove / cancel-invitation confirmation. */}
        <AlertDialog
          open={removeDialogFor !== null}
          onOpenChange={(open) => {
            if (!open) setRemoveDialogFor(null);
          }}
        >
          <AlertDialogContent>
            {removeDialogFor ? (
              <>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    {removeDialogFor.user.is_pending
                      ? t("cancel_invitation_title")
                      : t("remove_member_title")}
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    {removeDialogFor.user.is_pending
                      ? t("cancel_invitation_confirm", {
                          name: removeDialogFor.user.name,
                        })
                      : t("remove_member_confirm", {
                          name: removeDialogFor.user.name,
                        })}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={async () => {
                      const m = removeDialogFor;
                      setRemoveDialogFor(null);
                      await removeMember(m);
                    }}
                  >
                    {removeDialogFor.user.is_pending
                      ? t("cancel_invitation_action")
                      : t("remove_member_action")}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </>
            ) : null}
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}

function ChangeRoleDialog({
  membership,
  roles,
  departmentId,
  onClose,
  onChanged,
}: {
  membership: DepartmentMembership | null;
  roles: DepartmentRole[];
  departmentId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [roleId, setRoleId] = useState<string>("");
  const [saving, setSaving] = useState(false);

  // Reset the picker to the member's current role each time the dialog
  // opens for a different membership.
  useEffect(() => {
    if (membership) setRoleId(membership.role_id);
  }, [membership]);

  async function save() {
    if (!membership || !roleId || roleId === membership.role_id) {
      onClose();
      return;
    }
    setSaving(true);
    try {
      await changeDepartmentMemberRole(departmentId, membership.user_id, roleId);
      toast.success(t("role_changed_toast"));
      onChanged();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={membership !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("change_role_title")}</DialogTitle>
          <DialogDescription>
            {membership
              ? t("change_role_subtitle", { name: membership.user.name })
              : null}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-2">
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
          <Button type="button" variant="ghost" onClick={onClose}>
            {tCommon("cancel")}
          </Button>
          <Button
            type="button"
            onClick={() => void save()}
            disabled={saving || !roleId}
          >
            {saving ? tCommon("loading") : tCommon("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
