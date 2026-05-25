"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { signIn } from "next-auth/react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Badge } from "@/components/ui/badge";
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
import { useAuth } from "@/features/auth/hooks/useAuth";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

type FormValues = z.infer<typeof schema>;

export default function HomePage() {
  const tApp = useTranslations("app");
  const tAuth = useTranslations("auth");
  const tErr = useTranslations("errors");
  const router = useRouter();
  const auth = useAuth();
  const [submitting, setSubmitting] = useState(false);

  // Already signed in? Hop straight to the right destination. Multi-business
  // users land on `/businesses` so they can pick which one to work in;
  // mid-flow password resets still get pinned to `/change-password`.
  useEffect(() => {
    if (auth.status !== "authenticated" || !auth.user) return;
    router.replace(auth.user.must_change_password ? "/change-password" : "/businesses");
  }, [auth.status, auth.user, router]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: FormValues) {
    setSubmitting(true);
    try {
      const result = await signIn("credentials", {
        email: values.email,
        password: values.password,
        redirect: false,
      });
      if (!result || result.error) {
        toast.error(tAuth("invalid_credentials"));
        return;
      }
      // useAuth's useEffect picks up the new session + redirects.
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="text-base font-semibold tracking-tight">{tApp("name")}</span>
          <Badge variant="secondary">Phase 1</Badge>
        </div>
        <ThemeToggle />
      </header>

      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-16">
        <Card>
          <CardHeader>
            <CardTitle>{tAuth("title")}</CardTitle>
            <CardDescription>{tAuth("subtitle_password")}</CardDescription>
          </CardHeader>
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
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex items-center justify-between">
                        <FormLabel>{tAuth("password_label")}</FormLabel>
                        <Link
                          href="/reset-password"
                          className="text-muted-foreground hover:text-foreground text-xs"
                        >
                          {tAuth("forgot_password")}
                        </Link>
                      </div>
                      <FormControl>
                        <PasswordInput autoComplete="current-password" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" className="w-full" disabled={submitting}>
                  {submitting ? tAuth("signing_in") : tAuth("sign_in")}
                </Button>
              </form>
            </Form>

            {process.env.NEXT_PUBLIC_GOOGLE_SIGN_IN_ENABLED === "true" && (
              <>
                <div className="my-6 flex items-center gap-3">
                  <div className="bg-border h-px flex-1" />
                  <span className="text-muted-foreground text-xs uppercase tracking-wider">
                    {tAuth("or")}
                  </span>
                  <div className="bg-border h-px flex-1" />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() => signIn("google", { callbackUrl: "/businesses" })}
                  disabled={submitting}
                >
                  {tAuth("sign_in_with_google")}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
