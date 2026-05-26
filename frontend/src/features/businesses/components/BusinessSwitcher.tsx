"use client";

import { Building2, Check, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { BusinessLogo } from "@/features/businesses/components/BusinessLogo";
import { CreateBusinessDialog } from "@/features/businesses/components/CreateBusinessDialog";
import { useCurrentBusiness } from "@/features/businesses/hooks/useCurrentBusiness";

/**
 * Topbar dropdown that names the active business and lets the user switch.
 * CEO super-admins get a "+ Create business" entry; regular members don't.
 */
export function BusinessSwitcher({ canCreate }: { canCreate: boolean }) {
  const t = useTranslations("businesses");
  const { status, current, businesses, setCurrent, reload } = useCurrentBusiness();

  if (status === "loading") {
    return (
      <Button variant="ghost" size="sm" disabled>
        <Building2 className="mr-2 size-4" />
        {t("loading")}
      </Button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm">
          {current ? (
            <BusinessLogo
              logoUrl={current.logo_url}
              name={current.name}
              size={20}
              className="mr-2"
            />
          ) : (
            <Building2 className="mr-2 size-4" />
          )}
          <span className="max-w-[180px] truncate">
            {current?.name ?? t("none_selected")}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>{t("switch_title")}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {businesses.length === 0 ? (
          <DropdownMenuItem disabled>{t("none")}</DropdownMenuItem>
        ) : (
          businesses.map((b) => (
            <DropdownMenuItem
              key={b.id}
              onClick={() => setCurrent(b.id)}
              className="justify-between"
            >
              <span className="flex min-w-0 items-center gap-2">
                <BusinessLogo logoUrl={b.logo_url} name={b.name} size={18} />
                <span className="truncate">{b.name}</span>
              </span>
              {current?.id === b.id ? <Check className="size-4" /> : null}
            </DropdownMenuItem>
          ))
        )}
        {canCreate ? (
          <>
            <DropdownMenuSeparator />
            <CreateBusinessDialog
              trigger={
                <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                  <Plus className="mr-2 size-4" />
                  {t("create_action")}
                </DropdownMenuItem>
              }
              onCreated={() => void reload()}
            />
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
