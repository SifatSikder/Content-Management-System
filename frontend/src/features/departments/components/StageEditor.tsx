"use client";

import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  createStage,
  deleteStage,
  listStages,
  updateStage,
} from "@/features/departments/api";
import type { Stage } from "@/features/departments/types";
import { ApiError } from "@/lib/api-client";

function SortableStageRow({
  stage,
  onDelete,
}: {
  stage: Stage;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: stage.id });
  // `@dnd-kit/utilities` isn't a direct dep; format the transform manually
  // — it's just an x/y translation for vertical sorting.
  const transformStyle = transform
    ? `translate3d(${transform.x}px, ${transform.y}px, 0)`
    : undefined;
  const style: React.CSSProperties = {
    transform: transformStyle,
    transition,
    opacity: isDragging ? 0.6 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className="bg-card flex items-center gap-3 rounded-md border px-3 py-2"
    >
      <button
        type="button"
        className="text-muted-foreground hover:text-foreground cursor-grab active:cursor-grabbing"
        aria-label="Drag handle"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="size-4" />
      </button>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">
          {stage.name_i18n.en ?? stage.name_i18n.nl ?? stage.key}
        </div>
        <div className="text-muted-foreground font-mono text-xs">{stage.key}</div>
      </div>
      <Button variant="ghost" size="icon" onClick={onDelete} aria-label="Delete stage">
        <Trash2 className="size-4" />
      </Button>
    </div>
  );
}

export function StageEditor({ departmentId }: { departmentId: string }) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listStages(departmentId);
      setStages(res.items);
    } catch (exc) {
      toast.error(exc instanceof Error ? exc.message : tCommon("error"));
    } finally {
      setLoading(false);
    }
  }, [departmentId, tCommon]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = stages.findIndex((s) => s.id === active.id);
    const newIdx = stages.findIndex((s) => s.id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;
    const next = arrayMove(stages, oldIdx, newIdx);
    setStages(next);
    // Persist new order_index for every row that moved. Run sequentially —
    // the backend is single-row PATCH and we want any failure to surface
    // before issuing more writes.
    try {
      for (const [i, s] of next.entries()) {
        if (s.order_index !== i) {
          await updateStage(departmentId, s.id, { order_index: i });
        }
      }
    } catch (exc) {
      toast.error(exc instanceof Error ? exc.message : tCommon("error"));
      void load();
    }
  }

  async function handleDelete(stage: Stage) {
    try {
      await deleteStage(departmentId, stage.id);
      toast.success(t("stage_deleted_toast"));
      await load();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{t("stages_title")}</CardTitle>
            <CardDescription>{t("stages_subtitle")}</CardDescription>
          </div>
          <AddStageDialog departmentId={departmentId} onCreated={() => void load()} />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : stages.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("stages_empty")}</p>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={onDragEnd}
          >
            <SortableContext
              items={stages.map((s) => s.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {stages.map((s) => (
                  <SortableStageRow
                    key={s.id}
                    stage={s}
                    onDelete={() => void handleDelete(s)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </CardContent>
    </Card>
  );
}

function AddStageDialog({
  departmentId,
  onCreated,
}: {
  departmentId: string;
  onCreated: () => void;
}) {
  const t = useTranslations("departments");
  const tCommon = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [nameNl, setNameNl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createStage(departmentId, {
        key: key.trim(),
        name_i18n: { en: nameEn.trim(), nl: nameNl.trim() || nameEn.trim() },
      });
      toast.success(t("stage_added_toast"));
      setOpen(false);
      setKey("");
      setNameEn("");
      setNameNl("");
      onCreated();
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : tCommon("error");
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 size-4" />
          {t("add_stage")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("add_stage")}</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2">
            <Label htmlFor="stage-key">{t("key_label")}</Label>
            <Input
              id="stage-key"
              required
              pattern="^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="inbox"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="stage-name-en">{t("name_en_label")}</Label>
            <Input
              id="stage-name-en"
              required
              value={nameEn}
              onChange={(e) => setNameEn(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="stage-name-nl">{t("name_nl_label")}</Label>
            <Input
              id="stage-name-nl"
              value={nameNl}
              onChange={(e) => setNameNl(e.target.value)}
              placeholder={nameEn}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? tCommon("loading") : t("add_stage")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
