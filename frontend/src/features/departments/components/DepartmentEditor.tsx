"use client";

import { Check, ChevronDown, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { CAPABILITY_REGISTRY } from "@/features/capabilities/registry";
import { updateDepartment } from "@/features/departments/api";
import type { Department } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

/**
 * Rename + capability-picker editor for a single department.
 *
 * Capabilities are sourced from `CAPABILITY_REGISTRY` (the frontend mirror
 * of `app/capabilities/registry.py`). Unknown keys already set on the
 * department — e.g. a future capability the backend has but the frontend
 * doesn't ship yet — stay selectable and removable so admins are never
 * stuck with an orphan.
 */
export function DepartmentEditor({
  department,
  onChanged,
}: {
  department: Department;
  onChanged: (d: Department) => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [name, setName] = useState(department.name);
  const [selected, setSelected] = useState<string[]>(department.capabilities);
  const [saving, setSaving] = useState(false);

  // The picker shows every registry entry plus any unknown keys already set
  // on the department (so the user can still see + deselect them). Registry
  // order is preserved for the known set; unknown keys go at the end.
  const options = useMemo(() => {
    const known = Object.values(CAPABILITY_REGISTRY).map((entry) => ({
      key: entry.key,
      name: entry.name,
    }));
    const knownKeys = new Set(known.map((o) => o.key));
    const unknown = selected
      .filter((k) => !knownKeys.has(k))
      .map((k) => ({ key: k, name: k }));
    return [...known, ...unknown];
  }, [selected]);

  function toggle(key: string) {
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }

  function displayName(key: string): string {
    return CAPABILITY_REGISTRY[key]?.name ?? key;
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateDepartment(department.id, {
        name: name.trim(),
        capabilities: selected,
      });
      toast.success(t("saved_toast"));
      onChanged(updated);
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("editor_title")}</CardTitle>
        <CardDescription>{t("editor_subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={save}>
          <div className="space-y-2">
            <Label htmlFor="dept-name">{t("name_label")}</Label>
            <Input
              id="dept-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label>{t("capabilities_label")}</Label>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full justify-between font-normal"
                >
                  <span className={selected.length === 0 ? "text-muted-foreground" : ""}>
                    {selected.length === 0
                      ? t("capabilities_picker_placeholder")
                      : t("capabilities_count", { count: selected.length })}
                  </span>
                  <ChevronDown className="size-4 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                align="start"
                className="w-[var(--radix-popover-trigger-width)] p-1"
              >
                <ul className="flex flex-col">
                  {options.map((opt) => {
                    const checked = selected.includes(opt.key);
                    return (
                      <li key={opt.key}>
                        <button
                          type="button"
                          onClick={() => toggle(opt.key)}
                          className="hover:bg-accent flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm"
                        >
                          <Check
                            className={cn("size-4 shrink-0", checked ? "opacity-100" : "opacity-0")}
                          />
                          <span className="flex-1 truncate">{opt.name}</span>
                          <span className="text-muted-foreground ml-2 font-mono text-xs">
                            {opt.key}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </PopoverContent>
            </Popover>

            <div className="flex flex-wrap gap-1 pt-1">
              {selected.length === 0 ? (
                <span className="text-muted-foreground text-xs">{t("no_capabilities")}</span>
              ) : (
                selected.map((key) => (
                  <Badge key={key} variant="secondary" className="gap-1 pr-1">
                    {displayName(key)}
                    <button
                      type="button"
                      onClick={() => toggle(key)}
                      aria-label={t("capabilities_picker_remove", { name: displayName(key) })}
                      className="hover:bg-foreground/10 rounded-sm p-0.5"
                    >
                      <X className="size-3" />
                    </button>
                  </Badge>
                ))
              )}
            </div>
          </div>

          <Button type="submit" disabled={saving}>
            {saving ? tCommon("loading") : tCommon("save")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
