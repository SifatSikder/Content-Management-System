import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";

import { SessionProvider } from "@/components/layout/session-provider";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sons Real Estate CMS",
  description: "Content production CRM for Sons Real Estate",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body
        // Browser extensions (Bitdefender's "bis_skin_checked", Grammarly's
        // "data-gr-c-*", etc.) routinely inject attributes into the DOM before
        // React hydrates. <html> already has suppressHydrationWarning; mirroring
        // it on <body> covers the rest of the common injection points.
        suppressHydrationWarning
        className="min-h-full flex flex-col bg-background text-foreground"
      >
        <SessionProvider>
          <NextIntlClientProvider locale={locale} messages={messages}>
            <ThemeProvider
              attribute="class"
              defaultTheme="system"
              enableSystem
              disableTransitionOnChange
            >
              {children}
            </ThemeProvider>
          </NextIntlClientProvider>
        </SessionProvider>
        {/* Toaster lives at body-level (outside provider stack) so its portal
            target doesn't get torn down when providers re-render. Documented
            Sonner + App-Router pattern. */}
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
