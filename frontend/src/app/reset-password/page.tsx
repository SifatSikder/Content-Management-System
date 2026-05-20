"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
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
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { requestPasswordReset, resetPassword } from "@/features/auth/api";
import { ApiError } from "@/lib/api-client";

const MIN_PASSWORD_LENGTH = 8;

const requestSchema = z.object({ email: z.string().email() });

function buildSetSchema(messages: { mismatch: string; short: string }) {
  return z
    .object({
      password: z.string().min(MIN_PASSWORD_LENGTH, messages.short),
      confirm_password: z.string(),
    })
    .refine((d) => d.password === d.confirm_password, {
      message: messages.mismatch,
      path: ["confirm_password"],
    });
}

export default function ResetPasswordPage() {
  const tAuth = useTranslations("auth");
  const tCommon = useTranslations("common");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");

  return token ? (
    <SetNewPassword token={token} router={router} tAuth={tAuth} tCommon={tCommon} tErr={tErr} />
  ) : (
    <RequestReset tAuth={tAuth} tToast={tToast} tErr={tErr} />
  );
}

function RequestReset({
  tAuth,
  tToast,
  tErr,
}: {
  tAuth: ReturnType<typeof useTranslations>;
  tToast: ReturnType<typeof useTranslations>;
  tErr: ReturnType<typeof useTranslations>;
}) {
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  type FormValues = z.infer<typeof requestSchema>;
  const form = useForm<FormValues>({
    resolver: zodResolver(requestSchema),
    defaultValues: { email: "" },
  });

  async function onSubmit(values: FormValues) {
    setSubmitting(true);
    try {
      await requestPasswordReset({ email: values.email });
      toast.success(tToast("password_reset_sent"));
      setSent(true);
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>
            {sent ? tAuth("reset_inbox_title") : tAuth("reset_password_title")}
          </CardTitle>
          <CardDescription>
            {sent ? tAuth("reset_inbox_body") : tAuth("reset_password_subtitle")}
          </CardDescription>
        </CardHeader>
        {!sent && (
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tAuth("email_label")}</FormLabel>
                      <FormControl>
                        <Input
                          type="email"
                          autoComplete="email"
                          placeholder={tAuth("email_placeholder")}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" className="w-full" disabled={submitting}>
                  {tAuth("send_reset_link")}
                </Button>
              </form>
            </Form>
          </CardContent>
        )}
      </Card>
    </main>
  );
}

function SetNewPassword({
  token,
  router,
  tAuth,
  tCommon,
  tErr,
}: {
  token: string;
  router: ReturnType<typeof useRouter>;
  tAuth: ReturnType<typeof useTranslations>;
  tCommon: ReturnType<typeof useTranslations>;
  tErr: ReturnType<typeof useTranslations>;
}) {
  const [submitting, setSubmitting] = useState(false);
  const schema = buildSetSchema({
    mismatch: tAuth("passwords_dont_match"),
    short: tAuth("min_password_length"),
  });
  type FormValues = z.infer<typeof schema>;
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", confirm_password: "" },
  });

  async function onSubmit(values: FormValues) {
    setSubmitting(true);
    try {
      await resetPassword({ token, password: values.password });
      router.replace("/");
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
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>{tAuth("set_new_password")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="password"
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
    </main>
  );
}
