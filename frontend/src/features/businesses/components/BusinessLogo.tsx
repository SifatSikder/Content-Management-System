import { Building2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface Props {
  logoUrl: string | null | undefined;
  name: string;
  size?: number;
  maxWidth?: number;
  className?: string;
  rounded?: "md" | "full";
}

/**
 * Logo for a business. Renders an <img> when a signed URL is present,
 * otherwise falls back to the building icon.
 *
 * The image fixes its height to `size` and lets width follow the source's
 * natural aspect (capped by `maxWidth`, default = 4× height). The fallback
 * icon stays a square so empty rows don't collapse.
 */
export function BusinessLogo({
  logoUrl,
  name,
  size = 24,
  maxWidth,
  className,
  rounded = "md",
}: Props) {
  const radius = rounded === "full" ? "rounded-full" : "rounded-md";
  if (logoUrl) {
    const capW = maxWidth ?? size * 4;
    return (
      <span
        className={cn("inline-block shrink-0 overflow-hidden", radius, className)}
        style={{ height: size, width: capW }}
      >
        <img
          src={logoUrl}
          alt={name}
          className="block h-full w-full object-contain"
        />
      </span>
    );
  }
  return (
    <span
      className={cn(
        "text-muted-foreground bg-muted flex shrink-0 items-center justify-center",
        radius,
        className,
      )}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <Building2 style={{ width: size * 0.6, height: size * 0.6 }} />
    </span>
  );
}
