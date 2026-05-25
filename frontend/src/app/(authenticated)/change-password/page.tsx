"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { signIn, signOut } from "next-auth/react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { PasswordInput } from "@/components/ui/password-input";
import { changePassword } from "@/features/auth/api";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { ApiError } from "@/lib/api-client";

const MIN_PASSWORD_LENGTH = 8;

function buildSchema(messages: { mismatch: string; short: string }) {
  return z
    .object({
      current_password: z.string().min(1),
      new_password: z.string().min(MIN_PASSWORD_LENGTH, messages.short),
      confirm_password: z.string(),
    })
    .refine((d) => d.new_password === d.confirm_password, {
      message: messages.mismatch,
      path: ["confirm_password"],
    });
}

export default function ChangePasswordPage() {
  const tAuth = useTranslations("auth");
  const tCommon = useTranslations("common");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const router = useRouter();
  const auth = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const schema = buildSchema({
    mismatch: tAuth("passwords_dont_match"),
    short: tAuth("min_password_length"),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  async function onSubmit(values: FormValues) {
    if (!auth.user) return;
    setSubmitting(true);
    try {
      await changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      toast.success(tToast("password_changed"));

      // Refresh the session so must_change_password flips to false. The
      // simplest reliable way: sign out, sign back in with the new password.
      await signOut({ redirect: false });
      const result = await signIn("credentials", {
        email: auth.user.email,
        password: values.new_password,
        redirect: false,
      });
      if (result?.error) {
        router.replace("/");
        return;
      }
      router.replace("/businesses");
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.message);
      } else {
        toast.error(tErr("generic"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>{tAuth("change_password_title")}</CardTitle>
          <CardDescription>{tAuth("change_password_subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="current_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tAuth("current_password_label")}</FormLabel>
                    <FormControl>
                      <PasswordInput autoComplete="current-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="new_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tAuth("new_password_label")}</FormLabel>
                    <FormControl>
                      <PasswordInput autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="confirm_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tAuth("confirm_password_label")}</FormLabel>
                    <FormControl>
                      <PasswordInput autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? tCommon("loading") : tCommon("save")}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
