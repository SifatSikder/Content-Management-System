import type { MetadataRoute } from "next";

/**
 * PWA manifest — installable on iOS Safari + Chrome/Edge desktop + Android.
 *
 * Icons are SVG with `sizes: "any"` so a single source covers every install
 * surface (modern Android, iOS 17+, desktop). A separate maskable icon is
 * provided for Android's adaptive-icon mask (safe zone = inner 80%).
 *
 * `start_url` is `/projects` so the home-screen icon drops the user
 * straight onto the kanban — the login redirect picks up if they're
 * not authed.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Sons Real Estate CMS",
    short_name: "Sons RE",
    description: "Content production CRM for Sons Real Estate",
    start_url: "/projects",
    display: "standalone",
    background_color: "#fafafa",
    theme_color: "#0a0a0a",
    orientation: "any",
    icons: [
      { src: "/icons/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      {
        src: "/icons/icon-maskable.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
