"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Copy } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { inviteMember } from "@/features/team/api";
import type { TeamMember } from "@/features/team/types";
import { ApiError } from "@/lib/api-client";
import { ROLES, type Role } from "@/features/auth/constants";

const ROLE_OPTIONS = ROLES.filter((r): r is Exclude<Role, "ceo"> => r !== "ceo");

const schema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(120),
  role: z.enum(ROLE_OPTIONS as unknown as readonly [Role, ...Role[]]),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  onInvited: (member?: TeamMember) => void;
  trigger?: React.ReactNode;
}

export function InviteDialog({ onInvited, trigger }: Props) {
  const tAuth = useTranslations("auth");
  const tCommon = useTranslations("common");
  const tRoles = useTranslations("roles");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const [open, setOpen] = useState(false);
  const [fallbackUrl, setFallbackUrl] = useState<string | null>(null);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", name: "", role: "editor" },
  });

  async function onSubmit(values: FormValues) {
    setFallbackUrl(null);
    try {
      const resp = await inviteMember(values);
      toast.success(tToast("invite_sent"));
      if (resp.invite_url_for_admin) {
        setFallbackUrl(resp.invite_url_for_admin);
      } else {
        form.reset();
        setOpen(false);
        onInvited();
      }
    } catch (err) {
      if (err instanceof ApiError) toast.error(err.message);
      else toast.error(tErr("generic"));
    }
  }

  async function copyUrl() {
    if (!fallbackUrl) return;
    try {
      await navigator.clipboard.writeText(fallbackUrl);
      toast.success("Copied");
    } catch {
      /* ignore */
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setFallbackUrl(null);
          form.reset();
          onInvited();
        }
        setOpen(o);
      }}
    >
      <DialogTrigger asChild>{trigger ?? <Button>{tAuth("invite_member")}</Button>}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{tAuth("invite_member")}</DialogTitle>
          <DialogDescription>{tAuth("invite_member_subtitle")}</DialogDescription>
        </DialogHeader>
        {fallbackUrl ? (
          <div className="space-y-3">
            <p className="text-muted-foreground text-sm">{tAuth("invite_email_not_configured")}</p>
            <div className="bg-muted/40 break-all rounded-md border p-3 text-xs">
              {fallbackUrl}
            </div>
            <Button onClick={copyUrl} variant="outline" className="w-full">
              <Copy className="mr-2 size-4" />
              {tAuth("copy_link")}
            </Button>
          </div>
        ) : (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tAuth("invitee_name_label")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tAuth("email_label")}</FormLabel>
                    <FormControl>
                      <Input type="email" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="role"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tAuth("role_label")}</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {ROLE_OPTIONS.map((r) => (
                          <SelectItem key={r} value={r}>
                            {tRoles(r)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  {tCommon("cancel")}
                </Button>
                <Button type="submit" disabled={form.formState.isSubmitting}>
                  {tAuth("send_invitation")}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  );
}
