import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // The blueprint mandates "no TanStack Query — plain apiFetchAuthed +
      // useState/useEffect" (CLAUDE.md). That pattern intentionally calls
      // setState from within useEffect after an async fetch, which trips the
      // newer react-hooks rule. Disable globally so the project's own data-
      // fetching idiom passes lint.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
