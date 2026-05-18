/**
 * next-intl request config — server side.
 *
 * Phase 0: no locale-prefixed routing yet. Default to Dutch; English is opt-in
 * via cookie / sessionStorage (Phase 1 wires the toggle). For now, locale is
 * fixed to Dutch on every request.
 */

import { getRequestConfig } from "next-intl/server";

export const SUPPORTED_LOCALES = ["nl", "en"] as const;
export const DEFAULT_LOCALE: (typeof SUPPORTED_LOCALES)[number] = "nl";

export default getRequestConfig(async () => {
  const locale = DEFAULT_LOCALE;
  const messages = (await import(`../../messages/${locale}.json`)).default;
  return { locale, messages };
});
