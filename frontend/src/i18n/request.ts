/**
 * next-intl request config — server side.
 *
 * Locale resolution order:
 *   1. The `sre.locale` cookie (set by the user via the locale switcher).
 *   2. `Settings.default_locale` — currently fixed to `nl`.
 *
 * The session-storage JWT carries the locale too (so the user's `Settings`
 * page can reflect it), but for SSR we only read cookies — sessionStorage is
 * unavailable on the server.
 */

import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

export const SUPPORTED_LOCALES = ["nl", "en"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: SupportedLocale = "nl";
export const LOCALE_COOKIE = "sre.locale";

function isSupported(value: string | undefined): value is SupportedLocale {
  return value === "nl" || value === "en";
}

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get(LOCALE_COOKIE)?.value;
  const locale: SupportedLocale = isSupported(cookieLocale) ? cookieLocale : DEFAULT_LOCALE;
  const messages = (await import(`../../messages/${locale}.json`)).default;
  return { locale, messages };
});
