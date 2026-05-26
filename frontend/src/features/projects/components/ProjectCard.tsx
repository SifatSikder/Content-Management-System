"use client";

import { useDraggable } from "@dnd-kit/core";
import { Calendar } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { StageAssigneesPopover } from "@/features/projects/components/StageAssigneesPopover";
import type { Project } from "@/features/projects/types";
import { cn } from "@/lib/utils";

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

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: project.id,
    data: { stageKey: project.stage_key },
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
      </Link>
      <div className="pt-2">
        <StageAssigneesPopover project={project} compact />
      </div>
    </Card>
  );
}
