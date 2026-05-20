"use client";

import { Kanban, LayoutDashboard, Menu, Settings, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import type { AuthUser } from "@/features/auth/types";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  labelKey: "kanban" | "dashboard" | "team" | "settings";
  icon: React.ComponentType<{ className?: string }>;
  ceoOnly?: boolean;
}

const ALL_NAV_ITEMS: readonly NavItem[] = [
  { href: "/projects", labelKey: "kanban", icon: Kanban },
  { href: "/dashboard", labelKey: "dashboard", icon: LayoutDashboard },
  { href: "/team", labelKey: "team", icon: Users, ceoOnly: true },
  { href: "/settings", labelKey: "settings", icon: Settings },
];

function visibleNavItems(role: string): readonly NavItem[] {
  return ALL_NAV_ITEMS.filter((item) => !item.ceoOnly || role === "ceo");
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function NavList({ role, onNavigate }: { role: string; onNavigate?: () => void }) {
  const t = useTranslations("shell");
  const pathname = usePathname();
  const items = visibleNavItems(role);
  return (
    <nav className="flex flex-col gap-1 p-3">
      {items.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" />
            {t(item.labelKey)}
          </Link>
        );
      })}
    </nav>
  );
}

function UserMenu({ user }: { user: AuthUser }) {
  const tShell = useTranslations("shell");
  const tAuth = useTranslations("auth");
  const tRoles = useTranslations("roles");
  const tToast = useTranslations("toast");
  const router = useRouter();
  const auth = useAuth();
  const handleLogout = async () => {
    const { toast } = await import("sonner");
    await auth.logout();
    toast.success(tToast("logged_out"));
    router.replace("/");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={tShell("user_menu")}>
          <Avatar className="size-8">
            <AvatarFallback>{initials(user.name)}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <div className="flex flex-col">
            <span className="text-sm font-medium">{user.name}</span>
            <span className="text-muted-foreground text-xs">{user.email}</span>
            <Badge variant="outline" className="mt-2 w-fit">
              {tRoles(user.role)}
            </Badge>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout}>{tAuth("logout")}</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ user, children }: { user: AuthUser; children: React.ReactNode }) {
  const tApp = useTranslations("app");
  const tShell = useTranslations("shell");
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r md:flex md:flex-col">
        <div className="flex h-14 items-center border-b px-4">
          <span className="text-sm font-semibold tracking-tight">{tApp("name")}</span>
        </div>
        <NavList role={user.role} />
      </aside>

      <div className="flex flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-14 items-center justify-between border-b px-4 md:px-6">
          <div className="flex items-center gap-2">
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="md:hidden"
                  aria-label={tShell("user_menu")}
                >
                  <Menu className="size-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0">
                <SheetTitle className="sr-only">{tApp("name")}</SheetTitle>
                <div className="flex h-14 items-center border-b px-4">
                  <span className="text-sm font-semibold">{tApp("name")}</span>
                </div>
                <NavList role={user.role} onNavigate={() => setSheetOpen(false)} />
              </SheetContent>
            </Sheet>
            <span className="text-sm font-semibold md:hidden">{tApp("name")}</span>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <UserMenu user={user} />
          </div>
        </header>

        <main className="flex-1">{children}</main>

        {/* Mobile bottom nav — limit to 4 items max for thumb reach */}
        <nav className="bg-background sticky bottom-0 grid auto-cols-fr grid-flow-col border-t md:hidden">
          {visibleNavItems(user.role).map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="text-muted-foreground hover:text-foreground flex flex-col items-center gap-1 py-2 text-xs"
              >
                <Icon className="size-5" />
                {tShell(item.labelKey)}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
