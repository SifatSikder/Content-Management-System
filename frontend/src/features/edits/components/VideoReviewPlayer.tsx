"use client";

import { Pause, Play } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { addEditComment, getPlaybackUrl } from "@/features/edits/api";
import type { EditComment, EditVersion } from "@/features/edits/types";

export interface VideoReviewPlayerHandle {
  seekTo: (seconds: number) => void;
}

interface Props {
  edit: EditVersion;
  comments: EditComment[];
  onCommentAdded: (c: EditComment) => void;
}

function fmt(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export const VideoReviewPlayer = forwardRef<VideoReviewPlayerHandle, Props>(
  function VideoReviewPlayer({ edit, comments, onCommentAdded }, ref) {
    const t = useTranslations("edits");
    const tToast = useTranslations("toast");
    const tErr = useTranslations("errors");
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const [url, setUrl] = useState<string | null>(null);
    const [duration, setDuration] = useState(0);
    const [current, setCurrent] = useState(0);
    const [playing, setPlaying] = useState(false);
    const [popoverTime, setPopoverTime] = useState<number | null>(null);
    const [draft, setDraft] = useState("");

    useImperativeHandle(ref, () => ({
      seekTo(seconds: number) {
        const v = videoRef.current;
        if (!v) return;
        v.currentTime = seconds;
        // play() rejects with NotSupportedError when the source can't be
        // decoded (common against fake-gcs-server placeholder bytes in dev).
        // Swallow — the <video onError> handler surfaces a UI-visible error.
        v.play().catch(() => {});
      },
    }));

    useEffect(() => {
      let cancelled = false;
      void getPlaybackUrl(edit.id).then((resp) => {
        if (!cancelled) setUrl(resp.url);
      });
      return () => {
        cancelled = true;
      };
    }, [edit.id]);

    const onTimelineClick = useCallback(
      (e: React.MouseEvent<HTMLDivElement>) => {
        if (!duration) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        const target = Math.max(0, Math.min(duration, pct * duration));
        setPopoverTime(target);
      },
      [duration],
    );

    async function submitComment() {
      if (popoverTime === null || !draft.trim()) return;
      try {
        const created = await addEditComment(edit.id, draft.trim(), popoverTime);
        onCommentAdded(created);
        toast.success(tToast("comment_added"));
        setDraft("");
        setPopoverTime(null);
      } catch {
        toast.error(tErr("generic"));
      }
    }

    if (!url) {
      return <Skeleton className="aspect-video w-full" />;
    }

    return (
      <div className="space-y-3">
        <div className="bg-black/95 relative aspect-video w-full overflow-hidden rounded-md">
          <video
            ref={videoRef}
            src={url}
            className="h-full w-full"
            onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
            onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onError={() => setPlaying(false)}
            playsInline
            controls={false}
          />
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="icon"
            variant="ghost"
            aria-label={playing ? "Pause" : "Play"}
            onClick={() => {
              const v = videoRef.current;
              if (!v) return;
              if (v.paused) v.play().catch(() => {});
              else v.pause();
            }}
          >
            {playing ? <Pause className="size-5" /> : <Play className="size-5" />}
          </Button>
          <span className="text-muted-foreground w-20 text-xs tabular-nums">
            {fmt(current)} / {fmt(duration)}
          </span>
          <Popover open={popoverTime !== null} onOpenChange={(o) => !o && setPopoverTime(null)}>
            <PopoverTrigger asChild>
              <div
                role="slider"
                aria-label="Timeline"
                aria-valuenow={current}
                aria-valuemin={0}
                aria-valuemax={duration}
                tabIndex={0}
                className="bg-muted relative h-2 flex-1 cursor-crosshair overflow-hidden rounded"
                onClick={onTimelineClick}
              >
                <div
                  className="bg-foreground/70 absolute inset-y-0 left-0"
                  style={{ width: `${duration ? (current / duration) * 100 : 0}%` }}
                />
                {comments.map((c) => (
                  <span
                    key={c.id}
                    title={c.body}
                    className="bg-primary absolute top-0 h-full w-0.5"
                    style={{
                      left: `${duration ? (c.timestamp_seconds / duration) * 100 : 0}%`,
                    }}
                  />
                ))}
              </div>
            </PopoverTrigger>
            {popoverTime !== null && (
              <PopoverContent className="w-72">
                <p className="text-muted-foreground mb-2 text-xs">
                  {t("add_comment_at", { time: fmt(popoverTime) })}
                </p>
                <Textarea
                  rows={3}
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                />
                <div className="mt-2 flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setDraft("");
                      setPopoverTime(null);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button size="sm" onClick={submitComment} disabled={!draft.trim()}>
                    Add
                  </Button>
                </div>
              </PopoverContent>
            )}
          </Popover>
        </div>
      </div>
    );
  },
);
