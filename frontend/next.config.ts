import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  // React Compiler (beta) auto-memoizes referential identity, which conflicts
  // with Radix UI's portal-mount strategy in React 19 + Next 16 Turbopack.
  // Documented symptom: "Failed to execute 'removeChild' on 'Node'" thrown
  // by the dev overlay on pages containing Dialog/AlertDialog/Sheet/Popover.
  // Disable until the React Compiler + Radix combo stabilises.
  // reactCompiler: true,
};

export default withNextIntl(nextConfig);
