import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: {
        "2xl": "1280px",
      },
    },
    extend: {
      colors: {
        // ── shadcn / Radix primitives ──────────────────────────────────────────
        border:      "rgb(var(--border) / <alpha-value>)",
        input:       "rgb(var(--input) / <alpha-value>)",
        ring:        "rgb(var(--ring) / <alpha-value>)",
        background:  "rgb(var(--background) / <alpha-value>)",
        foreground:  "rgb(var(--foreground) / <alpha-value>)",
        primary: {
          DEFAULT:    "rgb(var(--primary) / <alpha-value>)",
          foreground: "rgb(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT:    "rgb(var(--secondary) / <alpha-value>)",
          foreground: "rgb(var(--secondary-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT:    "rgb(var(--destructive) / <alpha-value>)",
          foreground: "rgb(var(--destructive-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT:    "rgb(var(--muted) / <alpha-value>)",
          foreground: "rgb(var(--muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT:    "rgb(var(--accent) / <alpha-value>)",
          foreground: "rgb(var(--accent-foreground) / <alpha-value>)",
        },
        popover: {
          DEFAULT:    "rgb(var(--popover) / <alpha-value>)",
          foreground: "rgb(var(--popover-foreground) / <alpha-value>)",
        },
        card: {
          DEFAULT:    "rgb(var(--card) / <alpha-value>)",
          foreground: "rgb(var(--card-foreground) / <alpha-value>)",
        },
        success: {
          DEFAULT:    "rgb(var(--success) / <alpha-value>)",
          foreground: "rgb(var(--success-foreground) / <alpha-value>)",
        },
        warning: {
          DEFAULT:    "rgb(var(--warning) / <alpha-value>)",
          foreground: "rgb(var(--warning-foreground) / <alpha-value>)",
        },
        danger: {
          DEFAULT:    "rgb(var(--danger) / <alpha-value>)",
          foreground: "rgb(var(--danger-foreground) / <alpha-value>)",
        },

        // ── TradeMentor financial tokens (flip light ↔ dark via CSS vars) ──────
        'tm-profit': "rgb(var(--tm-profit) / <alpha-value>)",
        'tm-loss':   "rgb(var(--tm-loss)   / <alpha-value>)",
        'tm-obs':    "rgb(var(--tm-obs)    / <alpha-value>)",
        'tm-brand':  "rgb(var(--tm-brand)  / <alpha-value>)",

        // ── Text hierarchy (3 tiers) ───────────────────────────────────────────
        // text-tm-primary   → headings, key data
        // text-tm-secondary → descriptions, supporting labels
        // text-tm-tertiary  → timestamps, metadata, placeholders
        'tm-primary':   "rgb(var(--text-primary)   / <alpha-value>)",
        'tm-secondary': "rgb(var(--text-secondary) / <alpha-value>)",
        'tm-tertiary':  "rgb(var(--text-tertiary)  / <alpha-value>)",

        // ── Layer system (use for elevated surfaces, overlays) ─────────────────
        'tm-surface':      "rgb(var(--layer-surface)       / <alpha-value>)",
        'tm-elevated':     "rgb(var(--layer-elevated)      / <alpha-value>)",
        'tm-overlay':      "rgb(var(--layer-overlay)       / <alpha-value>)",
        'tm-border-soft':  "rgb(var(--layer-border-subtle) / <alpha-value>)",
        'tm-sidebar':      "rgb(var(--sidebar-bg)          / <alpha-value>)",

        // ── Status system (use with opacity modifiers: /7, /20, /25) ──────────
        // e.g. bg-tm-status-danger/7  border-tm-status-danger/20  text-tm-status-danger
        'tm-status-danger':  "rgb(var(--status-danger)  / <alpha-value>)",
        'tm-status-caution': "rgb(var(--status-caution) / <alpha-value>)",
        'tm-status-success': "rgb(var(--status-success) / <alpha-value>)",
        'tm-status-info':    "rgb(var(--status-info)    / <alpha-value>)",
      },
      borderRadius: {
        lg:  "var(--radius)",
        md:  "calc(var(--radius) - 2px)",
        sm:  "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to:   { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to:   { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up":   "accordion-up 0.2s ease-out",
      },
      fontFamily: {
        // Inter for all UI text
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        // DM Mono for ALL financial numbers (₹, %, counts, P&L)
        mono: ["DM Mono", "Fira Code", "Cascadia Code", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
