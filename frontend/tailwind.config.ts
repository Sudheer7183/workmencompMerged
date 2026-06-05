import type { Config } from "tailwindcss";

/**
 * Tailwind configuration for the WC Premium Audit Platform.
 *
 * CRITICAL: All colour values reference CSS custom properties (--tokens)
 * rather than hardcoded hex values.  This ensures a single change to tokens.css
 * cascades everywhere — including Tailwind utility classes.
 *
 * No hardcoded hex values here or anywhere in src/components/ or src/features/.
 * The only permitted location for hardcoded hex is useTheme.ts (Addendum S4).
 */
const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      /**
       * Every colour key maps to a CSS custom property.
       * Usage in JSX: className="text-brand bg-surface border-border"
       */
      colors: {
        bg:           "var(--bg)",
        surface:      "var(--surface)",
        "surface-2":  "var(--surface-2)",
        border:       "var(--border)",
        "text-primary": "var(--text-primary)",
        muted:        "var(--text-muted)",
        brand:        "var(--brand)",
        "brand-dark": "var(--brand-dark)",
        accent:       "var(--accent)",
        green:        "var(--color-green)",
        amber:        "var(--color-amber)",
        red:          "var(--color-red)",
        blue:         "var(--color-blue)",
      },
      fontFamily: {
        sans: ["DM Sans", "sans-serif"],
        mono: ["DM Mono", "monospace"],
      },
      borderRadius: {
        sm:  "var(--radius-sm)",
        md:  "var(--radius-md)",
        lg:  "var(--radius-lg)",
        xl:  "var(--radius-xl)",
      },
      maxWidth: {
        content: "1360px",
      },
    },
  },
  plugins: [],
};

export default config;
