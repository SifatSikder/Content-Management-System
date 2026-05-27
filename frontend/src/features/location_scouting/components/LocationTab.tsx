"use client";

import { Camera, MapPin, Trash2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  createLocation,
  deleteLocation,
  deletePhoto,
  finalisePhoto,
  getPhotoUrl,
  initPhotoUpload,
  listLocations,
} from "@/features/location_scouting/api";
import { LockLocationButton } from "@/features/location_scouting/components/LockLocationButton";
import { performResumableUpload } from "@/features/asset_review_with_timecodes/lib/resumable-upload";
import type { Location, LocationPhoto } from "@/features/location_scouting/types";
import type { Project } from "@/features/projects/types";
import { ApiError } from "@/lib/api-client";

const PHOTO_ACCEPT = "image/jpeg,image/png,image/webp,image/heic";
const PHOTO_MAX_BYTES = 25 * 1024 * 1024;

interface Props {
  project: Project;
  /** When false, the tab renders read-only — no create form, no
   *  per-row controls, no Lock button. */
  canInput?: boolean;
  onProjectUpdated?: (next: Project) => void;
}

export function LocationTab({ project, canInput = true }: Props) {
  const t = useTranslations("locations");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");

  const [locations, setLocations] = useState<Location[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({
    address: "",
    contact_name: "",
    contact_phone: "",
    latitude: "",
    longitude: "",
  });

  const reload = useCallback(async () => {
    try {
      const items = await listLocations(project.id);
      setLocations(items);
    } catch {
      toast.error(tErr("generic"));
    }
  }, [project.id, tErr]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.address.trim()) return;
    setCreating(true);
    try {
      await createLocation(project.id, {
        address: draft.address.trim(),
        contact_name: draft.contact_name.trim() || null,
        contact_phone: draft.contact_phone.trim() || null,
        latitude: draft.latitude ? Number(draft.latitude) : null,
        longitude: draft.longitude ? Number(draft.longitude) : null,
      });
      setDraft({ address: "", contact_name: "", contact_phone: "", latitude: "", longitude: "" });
      toast.success(t("created"));
      await reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : tErr("generic");
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        {canInput ? <LockLocationButton project={project} /> : null}
      </div>
      {canInput && (
      <Card className="p-4">
        <form className="space-y-3" onSubmit={onCreate}>
          <div className="space-y-1.5">
            <Label htmlFor="loc-address">{t("address")}</Label>
            <Textarea
              id="loc-address"
              rows={2}
              value={draft.address}
              onChange={(e) => setDraft({ ...draft, address: e.target.value })}
              placeholder={t("address_placeholder")}
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="loc-contact-name">{t("contact_name")}</Label>
              <Input
                id="loc-contact-name"
                value={draft.contact_name}
                onChange={(e) => setDraft({ ...draft, contact_name: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="loc-contact-phone">{t("contact_phone")}</Label>
              <Input
                id="loc-contact-phone"
                type="tel"
                value={draft.contact_phone}
                onChange={(e) => setDraft({ ...draft, contact_phone: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="loc-lat">{t("latitude")}</Label>
              <Input
                id="loc-lat"
                type="number"
                step="any"
                value={draft.latitude}
                onChange={(e) => setDraft({ ...draft, latitude: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="loc-lng">{t("longitude")}</Label>
              <Input
                id="loc-lng"
                type="number"
                step="any"
                value={draft.longitude}
                onChange={(e) => setDraft({ ...draft, longitude: e.target.value })}
              />
            </div>
          </div>
          <Button type="submit" size="sm" disabled={creating || !draft.address.trim()}>
            {creating ? tCommon("loading") : t("add")}
          </Button>
        </form>
      </Card>
      )}

      {locations === null ? (
        <p className="text-muted-foreground text-sm">{tCommon("loading")}</p>
      ) : locations.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("empty")}</p>
      ) : (
        <div className="space-y-3">
          {locations.map((loc) => (
            <LocationRow
              key={loc.id}
              location={loc}
              canInput={canInput}
              onChanged={reload}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function LocationRow({
  location,
  canInput,
  onChanged,
}: {
  location: Location;
  canInput: boolean;
  onChanged: () => void;
}) {
  const t = useTranslations("locations");
  const tCommon = useTranslations("common");
  const tErr = useTranslations("errors");
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const mapsHref =
    location.latitude !== null && location.longitude !== null
      ? `https://www.google.com/maps/search/?api=1&query=${location.latitude},${location.longitude}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location.address)}`;

  async function onDelete() {
    setBusy(true);
    try {
      await deleteLocation(location.id);
      onChanged();
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(files: File[]) {
    // Multi-upload: run each file through the resumable pipeline in
    // sequence so we don't saturate the network on phones — real GCS
    // rate-limits aggressively on parallel uploads from one client.
    const valid = files.filter((f) => {
      if (f.size > PHOTO_MAX_BYTES) {
        toast.error(t("photo_too_large_named", { name: f.name }));
        return false;
      }
      return true;
    });
    if (valid.length === 0) return;

    setBusy(true);
    let succeeded = 0;
    try {
      for (const file of valid) {
        try {
          const init = await initPhotoUpload(location.id, {
            content_type: file.type,
            size_bytes: file.size,
          });
          await performResumableUpload({ sessionUrl: init.upload_session_url, file });
          await finalisePhoto(location.id, {
            gcs_bucket: init.gcs_bucket,
            gcs_object_name: init.gcs_object_name,
            content_type: file.type,
            size_bytes: file.size,
          });
          succeeded += 1;
        } catch {
          toast.error(t("photo_upload_failed_named", { name: file.name }));
        }
      }
      if (succeeded > 0) {
        toast.success(
          succeeded === 1
            ? t("photo_uploaded")
            : t("photos_uploaded_count", { count: succeeded }),
        );
        onChanged();
      }
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function onDeletePhoto(photoId: string) {
    setBusy(true);
    try {
      await deletePhoto(photoId);
      onChanged();
    } catch {
      toast.error(tErr("generic"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <a
            href={mapsHref}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-sm font-medium hover:underline"
          >
            <MapPin className="size-3.5" />
            {location.address}
          </a>
          {(location.contact_name || location.contact_phone) && (
            <p className="text-muted-foreground text-xs">
              {[location.contact_name, location.contact_phone].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        {canInput && (
          <div className="flex items-center gap-2">
            <ConfirmDialog
              title={t("delete_confirm")}
              confirmLabel={tCommon("delete")}
              onConfirm={onDelete}
            >
              <Button
                variant="ghost"
                size="icon"
                disabled={busy}
                aria-label={tCommon("delete")}
              >
                <Trash2 className="size-4" />
              </Button>
            </ConfirmDialog>
          </div>
        )}
      </div>

      <div className="space-y-2">
        {canInput && (
          <div className="flex items-center gap-2">
            <input
              ref={fileInput}
              type="file"
              accept={PHOTO_ACCEPT}
              multiple
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                if (files.length > 0) void onUpload(files);
              }}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInput.current?.click()}
              disabled={busy}
            >
              <Camera className="mr-1.5 size-4" />
              {t("add_photo")}
            </Button>
          </div>
        )}
        {location.photos.length > 0 && (
          <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
            {location.photos.map((p) => (
              <PhotoTile
                key={p.id}
                photo={p}
                onDelete={() => onDeletePhoto(p.id)}
                disabled={busy || !canInput}
              />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function PhotoTile({
  photo,
  onDelete,
  disabled,
}: {
  photo: LocationPhoto;
  onDelete: () => void;
  disabled: boolean;
}) {
  const t = useTranslations("locations");
  const tCommon = useTranslations("common");
  const [src, setSrc] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { url } = await getPhotoUrl(photo.id);
        if (!cancelled) setSrc(url);
      } catch {
        if (!cancelled) setErrored(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [photo.id]);

  return (
    <div className="bg-muted relative aspect-square overflow-hidden rounded">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          className="size-full object-cover"
          onError={() => setErrored(true)}
        />
      ) : errored ? (
        <div className="text-muted-foreground flex h-full items-center justify-center text-[10px]">
          ⚠
        </div>
      ) : (
        <div className="bg-muted-foreground/10 size-full animate-pulse" />
      )}
      <ConfirmDialog
        title={t("delete_photo_confirm")}
        confirmLabel={tCommon("delete")}
        onConfirm={onDelete}
      >
        <button
          type="button"
          disabled={disabled}
          className="bg-background/90 hover:bg-background absolute top-1 right-1 rounded-full p-0.5 disabled:opacity-50"
          aria-label={tCommon("delete")}
        >
          <X className="size-3" />
        </button>
      </ConfirmDialog>
    </div>
  );
}
