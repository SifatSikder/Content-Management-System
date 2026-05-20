"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { signIn } from "next-auth/react";
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
import { acceptInvite } from "@/features/auth/api";
import { ApiError } from "@/lib/api-client";

const MIN_PASSWORD_LENGTH = 8;

function buildSchema(messages: { mismatch: string; short: string }) {
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

export default function AcceptInvitePage() {
  const tAuth = useTranslations("auth");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");
  const [submitting, setSubmitting] = useState(false);

  const schema = buildSchema({
    mismatch: tAuth("passwords_dont_match"),
    short: tAuth("min_password_length"),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", confirm_password: "" },
  });

  if (!token) {
    return (
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-16">
        <Card>
          <CardHeader>
            <CardTitle>{tAuth("invite_invalid")}</CardTitle>
          </CardHeader>
        </Card>
      </main>
    );
  }

  async function onSubmit(values: FormValues) {
    setSubmitting(true);
    try {
      const result = await acceptInvite({ token: token!, password: values.password });
      const email = (result as { email?: string }).email;
      if (email) {
        // Auto-sign-in with the freshly-set password.
        const signin = await signIn("credentials", {
          email,
          password: values.password,
          redirect: false,
        });
        if (!signin?.error) {
          router.replace("/projects");
          return;
        }
      }
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
          <CardTitle>{tAuth("accept_invite_title")}</CardTitle>
          <CardDescription>{tAuth("accept_invite_subtitle")}</CardDescription>
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
                      <Input type="password" autoComplete="new-password" {...field} />
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
                      <Input type="password" autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? tCommon("loading") : tAuth("accept_invite_button")}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </main>
  );
}
