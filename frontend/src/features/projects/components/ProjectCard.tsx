"use client";

import { useDraggable } from "@dnd-kit/core";
import { Calendar } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Project } from "@/features/projects/types";
import { cn } from "@/lib/utils";

function initials(id: string): string {
  return id.slice(0, 2).toUpperCase();
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" });
}

interface Props {
  project: Project;
  draggable?: boolean;
}

export function ProjectCard({ project, draggable = true }: Props) {
  const tCat = useTranslations("categories");
  const tCommon = useTranslations("common");

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: project.id,
    data: { stage: project.stage },
    disabled: !draggable,
  });

  return (
    <Card
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={cn(
        "group cursor-grab touch-none p-3 transition-shadow active:cursor-grabbing",
        isDragging && "opacity-50 shadow-lg",
      )}
    >
      <Link
        href={`/projects/${project.id}`}
        onClick={(e) => {
          // Suppress click during drag — dnd-kit fires click after drop.
          if (isDragging) e.preventDefault();
        }}
        className="block space-y-2"
      >
        <div className="line-clamp-2 text-sm leading-snug font-medium">{project.title}</div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="text-[10px]">
            {tCat(project.category)}
          </Badge>
          {project.due_date && (
            <span className="text-muted-foreground flex items-center gap-1 text-[11px]">
              <Calendar className="size-3" />
              {formatDate(project.due_date)}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between pt-1">
          <Avatar className="size-6">
            <AvatarFallback className="text-[10px]">{initials(project.owner_id)}</AvatarFallback>
          </Avatar>
          <span className="text-muted-foreground text-[10px]">
            {tCommon("updated_at" in (tCommon as unknown as Record<string, string>) ? "updated_at" : "by")}
          </span>
        </div>
      </Link>
    </Card>
  );
}
