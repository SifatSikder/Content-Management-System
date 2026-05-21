"use client";

import { Download, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * Captures Chrome/Edge's `beforeinstallprompt` and exposes a discreet
 * banner inviting the user to add the PWA to their home screen.
 *
 * - iOS Safari doesn't fire this event (Apple route is Share → Add to Home
 *   Screen); we don't try to coach users through that here.
 * - We dismiss with sessionStorage so the banner doesn't follow you around
 *   in the same tab after you've clicked it away.
 */

const DISMISS_KEY = "sre.installPromptDismissed";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

export function InstallPrompt() {
  const t = useTranslations("pwa");
  const [evt, setEvt] = useState<BeforeInstallPromptEvent | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (sessionStorage.getItem(DISMISS_KEY) === "1") {
      setHidden(true);
      return;
    }
    const onBefore = (e: Event) => {
      e.preventDefault();
      setEvt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBefore);
    return () => window.removeEventListener("beforeinstallprompt", onBefore);
  }, []);

  if (hidden || !evt) return null;

  return (
    <div className="bg-background pointer-events-auto fixed right-4 bottom-4 z-40 flex max-w-sm items-center gap-3 rounded-lg border p-3 shadow-lg">
      <Download className="size-4 shrink-0" />
      <div className="flex-1 text-sm">
        <p className="font-medium">{t("install_title")}</p>
        <p className="text-muted-foreground text-xs">{t("install_body")}</p>
      </div>
      <Button
        size="sm"
        onClick={async () => {
          await evt.prompt();
          await evt.userChoice;
          setEvt(null);
        }}
      >
        {t("install_button")}
      </Button>
      <button
        type="button"
        aria-label={t("dismiss")}
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, "1");
          setHidden(true);
        }}
        className="text-muted-foreground hover:text-foreground"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}
