# TradeMentor AI — Design System (Current Implementation)
*Universal design tokens and component specs based on the implemented "Soft Precision" prototype in `shared.css`.*

---

## 1. Color Tokens

### Light Theme UI Structure
The current interface uses a clean, light-mode structural approach. Both the sidebar and the main content area use light surface colors, set against an off-white background with a soft Indigo accent header.

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `--bg` | Application background | `#F8FAFC` | `bg-slate-50` |
| `--surface` | Card surfaces, sidebar, bottom nav | `#FFFFFF` | `bg-white` |
| `--border` | Primary borders on cards and inputs | `#E2E8F0` | `border-slate-200` |
| `--border-soft` | Subtle dividers, sidebar borders | `#F1F5F9` | `border-slate-100` |

### General Text

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `--text` | Primary readable text, headings | `#0F172A` | `text-slate-900` |
| `--text-muted` | Body text, labels, secondary info | `#64748B` | `text-slate-500` |
| `--text-faint` | Placeholder text, muted labels | `#94A3B8` | `text-slate-400` |

### Brand — Indigo

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `--brand` | Primary buttons, active tabs, highlights | `#4F46E5` | `text-indigo-600` / `bg-indigo-600` |
| `--brand-mid` | Secondary interactive states | `#6366F1` | `bg-indigo-500` |
| `--brand-light` | Active nav backgrounds, light chips | `#EEF2FF` | `bg-indigo-50` |

### Financial Semantic — LOCKED
**Never use these colors for anything that is not actual profit or loss.**

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `--profit` | Positive P&L, gains, live dots | `#059669` | `text-emerald-600` |
| `--profit-bg` | Background tint for positive P&L | `#ECFDF5` | `bg-emerald-50` |
| `--loss` | Negative P&L, losses | `#DC2626` | `text-red-600` |
| `--loss-bg` | Background tint for negative P&L | `#FEF2F2` | `bg-red-50` |

### Behavioral Observation — Amber

| Token | Purpose | Hex | Tailwind approx |
|-------|---------|-----|----------------|
| `--obs` | Alerts, warnings, observations | `#D97706` | `text-amber-600` |
| `--obs-bg` | Background tint for alerts | `#FFFBEB` | `bg-amber-50` |

---

## 2. Elevation / Shadows
The current shadows use a sleek, minimal spread with low opacity pure black.

- **`--shadow-sm`**: `0 1px 2px rgba(0,0,0,0.05)` (Buttons, flat cards)
- **`--shadow-card`**: `0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.03)` (Default data cards)
- **`--shadow-lift`**: `0 8px 24px -4px rgba(0,0,0,0.07), 0 2px 8px -2px rgba(0,0,0,0.04)` (Card hover states)

---

## 3. Radii & Shape Language
- **`--radius-sm` (8px):** Input fields, secondary buttons, inner chips.
- **`--radius-md` (12px):** Primary data cards and dashboard widgets.
- **`--radius-lg` (16px):** Modals, large floating wrappers.

---

## 4. Typography

**Font family: Inter** is used for all UI elements (Headings, body, labels).
For all financial data (prices, P&L, timestamps, quantities), the `tabular-nums` property is heavily enforced via `.tabular` classes to prevent width shifting.

---

## 5. Background Accents
The top of the dashboard utilizes a soft, angled indigo gradient that fades into the Slate-50 background. 

```css
.bg-stripe-header {
  height: 280px;
  background: linear-gradient(172deg,
    rgba(238, 242, 255, 0.9) 0%,
    rgba(244, 246, 252, 0.7) 45%,
    rgba(248, 250, 252, 0.0) 100%
  );
}
```

---

## 6. Structural Components

### Layout Tokens
- **`--sidebar-w`**: 260px width for desktop side navigation. Set against white (`--surface`).
- **`--bottom-nav-h`**: 60px height for mobile bottom navigation.
- **Page Transitions**: Built-in 0.2s cubic-bezier(`0.4, 0, 0.2, 1`) transition system for hovers and links.

### The "No-Decoration" Data Rules
- All tables rely strictly on `--border-soft` with `padding: 13px 14px`. 
- Hovering over rows sets the row background to `#F8FAFC`.

*Note: All current classes and HTML elements have been mapped cleanly with Tailwind. The codebase should strictly reference the variables defined in `shared.css` to maintain visual consistency.*
