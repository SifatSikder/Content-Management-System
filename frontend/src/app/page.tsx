import { useTranslations } from "next-intl";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  const tApp = useTranslations("app");
  const tHome = useTranslations("home");

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="text-base font-semibold tracking-tight">{tApp("name")}</span>
          <Badge variant="secondary">Phase 0</Badge>
        </div>
        <ThemeToggle />
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-6 py-16">
        <Card>
          <CardHeader>
            <CardTitle>{tHome("title")}</CardTitle>
            <CardDescription>{tApp("tagline")}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground text-sm">{tHome("scaffold_note")}</p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
