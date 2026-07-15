# Design System Inspired by Sensibull

> Auto-extracted from `https://sensibull.com/#pricing` on 2026-06-14

## 1. Visual Theme & Atmosphere

Friendly, approachable design with rounded shapes and generous whitespace.

The hero section leads with "Trade Options with Clarity and Control" followed by "Build winning strategies, predict market trends, analyse your trades, and make informed decisions. P".

**Key Characteristics:**
- Inter as the heading font (custom web font loaded via @font-face)
- Inter as the body font for all running text
- Heading weight 300, letter-spacing 0.12px
- Light/white background (#ffffff) as the primary canvas
- Primary accent `#3488e8` used for CTAs and brand highlights
- 8 shadow level(s) detected — tinted shadows
- Rounded corners (8px+) creating a friendly, approachable feel
- Tags: light, rounded, colorful, sans-serif

## 2. Color Palette & Roles

### Primary
- **Primary Accent** (`#3488e8`) · `--color-primary`: Brand color, CTA backgrounds, link text, interactive highlights.
- **Secondary Accent** (`#4e7cb1`) · `--color-secondary`: Secondary brand, hover states, complementary highlights.
- **Background** (`#ffffff`) · `--color-bg`: Page background, primary canvas.
- **Background Secondary** (`#121416`) · `--color-bg-secondary`: Cards, surfaces, alternating sections.

### Text
- **Text Primary** (`#d0d1d2`) · `--color-text`: Headings and body text.
- **Text Secondary** (`#666666`) · `--color-text-secondary`: Muted text, captions, placeholders.

### Borders & Surfaces
- **Border** (`#1e2124`) · `--color-border`: Dividers, outlines, input borders.

### Full Extracted Palette

| # | Hex | CSS Variable | Role | Area | Contrast |
|---|---|---|---|---|---|
| 1 | `#1e2124` | `--palette-1` | button | large | text-light |
| 2 | `#121416` | `--palette-2` | section | large | text-light |
| 3 | `#c5f8f9` | `--palette-3` | section | large | text-dark |
| 4 | `#4e7cb1` | `--palette-4` | block | large | text-light |
| 5 | `#526780` | `--palette-5` | block | large | text-light |
| 6 | `#53bcc6` | `--palette-6` | block | medium | text-dark |
| 7 | `#3488e8` | `--palette-7` | button | medium | text-light |
| 8 | `#ffe178` | `--palette-8` | text-accent | medium | text-dark |
| 9 | `#22303f` | `--palette-9` | button | medium | text-light |
| 10 | `#314256` | `--palette-10` | button | small | text-light |
| 11 | `#68a5ea` | `--palette-11` | text-accent | small | text-dark |
| 12 | `#ffdc61` | `--palette-12` | text-accent | small | text-dark |

## 3. Typography Rules

- **Heading Font:** `Inter` (web font)
- **Body Font:** `Inter` (web font)

### Type Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|---|---|---|---|---|---|
| H1 | Inter | 48px | 300 | 64px | 0.12px |
| H2 | Inter | 32px | 700 | 52px | 0.08px |
| H3 | Inter | 20px | 700 | 28px | 0.25px |
| Body | Inter | 14px | 600 | 20px | 0.25px |
| Small | Inter | 16px | 600 | 28px | 0.25px |

### Type Scale

| Token | Size | Suggested Usage |
|---|---|---|
| Display | `48px` | headings |
| H1 | `40px` | headings |
| H2 | `32px` | headings |
| H3 | `24px` | headings |
| H4 | `20px` | headings |
| Body L | `18px` | body / supporting text |
| Body | `16px` | body / supporting text |
| Small | `14px` | body / supporting text |
| XS | `13px` | body / supporting text |
| Caption | `12px` | body / supporting text |

## 4. Component Stylings

### Primary Button

```css
.btn-primary {
  background: #3488e8;
  color: #ffffff;
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  cursor: pointer;
}
```

### Ghost Button

```css
.btn-ghost {
  background: transparent;
  color: #d0d1d2;
  border-radius: 0px;
  padding: 0px 0px;
  font-size: 18px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Card

```css
.card {
  background: #1e2124;
  border-radius: 12px;
  padding: 28px;
  box-shadow: rgba(0, 0, 0, 0.8) 0px 12px 32px -8px;
}
```

## 5. Layout Principles

- **Base spacing unit:** `10px` — use multiples (20px, 30px, 40px, etc.)

### Spacing Scale (extracted from real elements)

| Token | Value | Role |
|---|---|---|
| spacing-1 | `10px` | element |
| spacing-2 | `8px` | element |
| spacing-3 | `28px` | card |
| spacing-4 | `4px` | element |
| spacing-5 | `12px` | element |
| spacing-6 | `6px` | element |
| spacing-7 | `24px` | card |
| spacing-8 | `48px` | card |

### Border Radius Scale

| Token | Value | Element |
|---|---|---|
| radius-button | `8px` | button |
| radius-button | `12px` | button |
| radius-card | `16px` | card |
| radius-subtle | `4px` | subtle |
| radius-card | `24px` | card |
| radius-card | `32px` | card |

## 6. Depth & Elevation

| Level | Shadow | Usage |
|---|---|---|
| Low | `rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0...` | Cards, subtle elevation |
| Low | `rgba(0, 0, 0, 0.2) 0px 0px 4px 0px, rgba(0, 0, 0, 0.75) 0px 12px 32px -8px` | Cards, subtle elevation |
| Deep | `rgba(0, 0, 0, 0.8) 0px 12px 32px -8px` | Hero sections, deep layers |
| Low | `rgba(0, 0, 0, 0.19) 0px 0px 1px 1px, rgba(0, 0, 0, 0.8) 0px 5px 16px -10px` | Cards, subtle elevation |
| Low | `rgba(0, 0, 0, 0.2) 0px 1px 2px 0px` | Cards, subtle elevation |


## 7. Do's and Don'ts

### Do
- Use `#ffffff` as the primary background color
- Use `Inter` for all headings and `Inter` for body text
- Use `#3488e8` as the single dominant accent/CTA color
- Maintain `10px` as the base spacing unit — all gaps should be multiples
- Use rounded corners (`8px`+) consistently for all interactive elements
- Embrace bold color combinations — playful energy is the point
- Apply the shadow system for elevation — use the extracted shadow values
- Use weight 300 for headings to match the brand's typographic voice

### Don't
- Don't use colors outside the extracted palette without justification
- Don't substitute Inter/Inter with generic alternatives
- Don't use irregular spacing — stick to 10px grid
- Don't use dark/black backgrounds — this is a light-themed design
- Don't use sharp corners — they feel hostile in this rounded design language
- Don't use pure black (#000000) for text — use `#d0d1d2` instead
- Don't add decorative elements not present in the original design — no badges, ribbons, banners, or ornaments unless the source site uses them
- Don't invent UI patterns the source site doesn't have — if the original has no NEW badge, don't add one just because a red is in the palette

## 8. Responsive Behavior

| Breakpoint | Width | Notes |
|---|---|---|
| Mobile | < 640px | Single column, stack sections, reduce font sizes ~80% |
| Tablet | 640–1024px | 2-column where appropriate, maintain spacing ratios |
| Desktop | 1024–1440px | Full layout as designed |
| Wide | > 1440px | Max-width container, center content |

- Touch targets: minimum 44×44px on mobile
- Maintain 10px base unit across breakpoints — only scale multipliers

## 9. Agent Prompt Guide

### Quick Color Reference

```
Background:  #ffffff
Text:        #d0d1d2
Accent:      #3488e8
Secondary:   #4e7cb1
Border:      #1e2124
```

### Example Prompts

1. "Build a hero section with a `#ffffff` background, `Inter` heading in `#d0d1d2`, and a `#3488e8` CTA button with 8px radius."
2. "Create a pricing card using background `#121416`, border `#1e2124`, `Inter` for text, and 30px padding."
3. "Design a navigation bar — `#ffffff` background, `#d0d1d2` links, `#3488e8` for active state."
4. "Build a feature grid with 3 columns, 30px gap, each card using the card component style."
5. "Create a footer with `#d0d1d2` background, `#ffffff` text, and 20px padding."

### Iteration Guide

1. Start with layout structure (sections, grid, spacing)
2. Apply colors from the palette — background first, then text, then accents
3. Set typography — font families, sizes from the type scale, weights
4. Add components — buttons, cards, inputs using the specs above
5. Apply border-radius consistently across all elements
6. Add shadows for depth — use the extracted shadow values, not defaults
7. Check responsive behavior — test mobile and tablet layouts
8. Final pass — verify all colors match, spacing is consistent, fonts are correct
