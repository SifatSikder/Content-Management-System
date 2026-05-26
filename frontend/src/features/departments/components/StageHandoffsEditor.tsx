"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  listRoles,
  listStageHandoffs,
  upsertStageHandoff,
} from "@/features/departments/api";
import type {
  DepartmentRole,
  StageHandoff,
} from "@/features/departments/types";
import {
  getStages,
  localizedStageLabel,
} from "@/features/projects/lib/stagesByTemplate";
import { ApiError } from "@/lib/api-client";

interface Props {
  departmentId: string;
  templateKey: string | null;
  locale?: string;
}

function roleLabel(role: DepartmentRole, locale: string): string {
  return (
    role.name_i18n[locale] ??
    role.name_i18n.en ??
    role.name_i18n.nl ??
    role.key
  );
}

/**
 * One row per stage in the department's template. Each row lets the
 * admin pick which role(s) get auto-assigned to the card when a project
 * enters that stage.
 */
export function StageHandoffsEditor({
  departmentId,
  templateKey,
  locale = "en",
}: Props) {
  const [handoffs, setHandoffs] = useState<StageHandoff[] | null>(null);
  const [roles, setRoles] = useState<DepartmentRole[] | null>(null);
  const [savingStage, setSavingStage] = useState<string | null>(null);

  const stages = useMemo(() => getStages(templateKey), [templateKey]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [h, r] = await Promise.all([
          listStageHandoffs(departmentId),
          listRoles(departmentId),
        ]);
        if (cancelled) return;
        setHandoffs(h.items);
        setRoles(r.items);
      } catch {
        if (cancelled) return;
        toast.error("Failed to load stage handoffs");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [departmentId]);

  async function saveHandoff(stageKey: string, roleIds: string[]) {
    setSavingStage(stageKey);
    try {
      const row = await upsertStageHandoff(departmentId, {
        stage_key: stageKey,
        role_ids: roleIds,
      });
      setHandoffs((prev) => {
        const base = prev ?? [];
        const without = base.filter((h) => h.stage_key !== stageKey);
        return [...without, row];
      });
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Failed to save handoff",
      );
    } finally {
      setSavingStage(null);
    }
  }

  if (handoffs === null || roles === null) {
    return <p className="text-muted-foreground text-sm">Loading…</p>;
  }
  if (stages.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        This template has no stages defined.
      </p>
    );
  }

  const handoffByStage = new Map(handoffs.map((h) => [h.stage_key, h]));
  const roleById = new Map(roles.map((r) => [r.id, r]));

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">Stage hand-offs</h3>
        <p className="text-muted-foreground text-xs">
          When a project enters a stage, the board auto-assigns every member
          who holds one of the roles you pick here.
        </p>
      </div>

      <ul className="divide-border divide-y rounded-md border">
        {stages.map((stage) => {
          const current = handoffByStage.get(stage.key);
          const roleIds = current?.role_ids ?? [];
          return (
            <li
              key={stage.key}
              className="flex items-start justify-between gap-3 p-3"
            >
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {localizedStageLabel(stage, locale, stage.key)}
                  </span>
                  <span className="text-muted-foreground font-mono text-[10px]">
                    {stage.key}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-1">
                  {roleIds.length === 0 ? (
                    <span className="text-muted-foreground text-xs">
                      (no auto-assign — falls back to project owner)
                    </span>
                  ) : (
                    roleIds.map((id) => {
                      const role = roleById.get(id);
                      return (
                        <Badge
                          key={id}
                          variant="secondary"
                          className="text-[10px]"
                        >
                          {role ? roleLabel(role, locale) : "(deleted role)"}
                        </Badge>
                      );
                    })
                  )}
                </div>
              </div>
              <Popover>
                <PopoverTrigger asChild>
                  <Button size="sm" variant="outline">
                    Edit roles
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-64 p-2" align="end">
                  <ul className="space-y-1">
                    {roles.map((role) => {
                      const checked = roleIds.includes(role.id);
                      return (
                        <li key={role.id}>
                          <button
                            type="button"
                            className="hover:bg-muted flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-xs"
                            disabled={savingStage === stage.key}
                            onClick={() => {
                              const next = checked
                                ? roleIds.filter((r) => r !== role.id)
                                : [...roleIds, role.id];
                              void saveHandoff(stage.key, next);
                            }}
                          >
                            <span className="truncate">
                              {roleLabel(role, locale)}
                            </span>
                            <span
                              className={
                                checked
                                  ? "text-primary font-medium"
                                  : "text-muted-foreground"
                              }
                            >
                              {checked ? "on" : "off"}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                    {roles.length === 0 ? (
                      <li className="text-muted-foreground p-2 text-xs">
                        No roles defined yet — add one in the Roles tab.
                      </li>
                    ) : null}
                  </ul>
                </PopoverContent>
              </Popover>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
