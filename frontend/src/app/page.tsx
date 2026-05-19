"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
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
import { requestLink } from "@/features/auth/api";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { ApiError } from "@/lib/api-client";

const schema = z.object({
  email: z.string().email(),
});

type FormValues = z.infer<typeof schema>;

export default function HomePage() {
  const tApp = useTranslations("app");
  const tAuth = useTranslations("auth");
  const tToast = useTranslations("toast");
  const tErr = useTranslations("errors");
  const router = useRouter();
  const auth = useAuth();
  const [submitted, setSubmitted] = useState(false);

  // Already signed in? Send them straight to the kanban.
  useEffect(() => {
    if (auth.status === "authenticated") {
      router.replace("/projects");
    }
  }, [auth.status, router]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  async function onSubmit(values: FormValues) {
    try {
      await requestLink({ email: values.email });
      setSubmitted(true);
      toast.success(tToast("magic_link_sent"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        toast.error(tErr("rate_limited"));
      } else {
        toast.error(tErr("generic"));
      }
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
            <CardTitle>{submitted ? tAuth("check_inbox_title") : tAuth("title")}</CardTitle>
            <CardDescription>
              {submitted ? tAuth("check_inbox_body") : tAuth("subtitle")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {submitted ? (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setSubmitted(false)}
              >
                {tAuth("send_again")}
              </Button>
            ) : (
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
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={form.formState.isSubmitting}
                  >
                    {tAuth("request_link")}
                  </Button>
                </form>
              </Form>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
