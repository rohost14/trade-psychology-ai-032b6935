---
name: design-dhan-co
description: Design system extracted from Dhan (https://dhan.co/). Use when building UI that should match this brand's visual identity.
triggers:
  - "Dhan"
  - "dhan-co"
  - "design like Dhan"
  - "Dhan風"
source: https://dhan.co/
extractedAt: 2026-06-14T14:43:55.752Z
tags: ["light", "rounded", "colorful", "serif"]
---
# Design System Inspired by Dhan

> Auto-extracted from `https://dhan.co/` on 2026-06-14

## 1. Visual Theme & Atmosphere

Friendly, approachable design with rounded shapes and generous whitespace.

The hero section leads with "Investing & Trading Platform for StocksOptionsFuturesCommodityETFsMutual FundsIPONFO".

**Key Characteristics:**
- CircularXXSub-Bold as the heading font (custom web font loaded via @font-face)
- ui-sans-serif as the body font for all running text
- Heading weight 400
- Light/white background (#ffffff) as the primary canvas
- Primary accent `#ef9309` used for CTAs and brand highlights
- 2 shadow level(s) detected — tinted shadows
- Rounded corners (8px+) creating a friendly, approachable feel
- Tags: light, rounded, colorful, serif

## 2. Color Palette & Roles

### Primary
- **Primary Accent** (`#ef9309`) · `--color-primary`: Brand color, CTA backgrounds, link text, interactive highlights.
- **Secondary Accent** (`#2196d4`) · `--color-secondary`: Secondary brand, hover states, complementary highlights.
- **Background** (`#ffffff`) · `--color-bg`: Page background, primary canvas.
- **Background Secondary** (`#000000`) · `--color-bg-secondary`: Cards, surfaces, alternating sections.

### Text
- **Text Primary** (`#000000`) · `--color-text`: Headings and body text.
- **Text Secondary** (`#666666`) · `--color-text-secondary`: Muted text, captions, placeholders.

### Borders & Surfaces
- **Border** (`#e5e5e5`) · `--color-border`: Dividers, outlines, input borders.

### Full Extracted Palette

| # | Hex | CSS Variable | Role | Area | Contrast |
|---|---|---|---|---|---|
| 1 | `#2a4665` | `--palette-1` | block | large | text-light |
| 2 | `#000000` | `--palette-2` | block | large | text-light |
| 3 | `#091227` | `--palette-3` | block | large | text-light |
| 4 | `#ef9309` | `--palette-4` | text-accent | medium | text-dark |
| 5 | `#ffffff` | `--palette-5` | button | medium | text-dark |
| 6 | `#2196d4` | `--palette-6` | button | medium | text-light |
| 7 | `#8751a8` | `--palette-7` | button | small | text-light |
| 8 | `#307d7d` | `--palette-8` | button | small | text-light |
| 9 | `#b2833e` | `--palette-9` | button | small | text-dark |
| 10 | `#7a663f` | `--palette-10` | button | small | text-light |
| 11 | `#0a2745` | `--palette-11` | text-accent | small | text-light |
| 12 | `#0874b0` | `--palette-12` | text-accent | small | text-light |
| 13 | `#17c185` | `--palette-13` | text-accent | small | text-dark |

## 3. Typography Rules

- **Heading Font:** `CircularXXSub-Bold` (web font)
- **Body Font:** `ui-sans-serif`, sans-serif

### Type Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|---|---|---|---|---|---|
| H1 | CircularXXSub-Bold | 40px | 400 | 52px | normal |
| H2 | CircularXXSub-Bold | 40px | 400 | 48px | normal |
| H3 | CircularXXSub-Medium | 36px | 400 | 52px | normal |
| Body | CircularXXSub-Medium | 16px | 400 | 24px | normal |
| Small | CircularXXSub-Bold | 14px | 400 | 20px | normal |
| Code | ui-monospace | 14px | 700 | 24px | normal |

### Type Scale

| Token | Size | Suggested Usage |
|---|---|---|
| Display | `48px` | headings |
| H1 | `40px` | headings |
| H2 | `30px` | headings |
| H3 | `28px` | headings |
| H4 | `24px` | headings |
| Body L | `20px` | body / supporting text |
| Body | `18px` | body / supporting text |
| Small | `16px` | body / supporting text |
| XS | `15px` | body / supporting text |
| Caption | `14px` | body / supporting text |

## 4. Component Stylings

### Primary Button

```css
.btn-primary {
  background: #ef9309;
  color: #0a2745;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 15px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Ghost Button

```css
.btn-ghost {
  background: transparent;
  color: #ffffff;
  border-radius: 0px;
  padding: 0px 12px;
  font-size: 16px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Filled Button

```css
.btn-filled {
  background: #ef9309;
  color: #ffffff;
  border-radius: 8px;
  padding: 10px 10px;
  font-size: 14px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Outline Button

```css
.btn-outline {
  background: transparent;
  color: #ffffff;
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 16px;
  font-weight: 400;
  border: 1px solid rgba(255, 255, 255, 0.1);
  cursor: pointer;
}
```

### Outline Button 2

```css
.btn-outline-2 {
  background: transparent;
  color: #051628;
  border-radius: 10px;
  padding: 12px 32px;
  font-size: 16px;
  font-weight: 400;
  border: 1px solid rgb(198, 137, 36);
  cursor: pointer;
}
```

### Filled Button 2

```css
.btn-filled-2 {
  background: #2196d4;
  color: #ffffff;
  border-radius: 10px;
  padding: 12px 32px;
  font-size: 16px;
  font-weight: 400;
  border: 1px solid rgb(43, 155, 209);
  cursor: pointer;
}
```

### Card

```css
.card {
  background: #fff1e0;
  border-radius: 24px;
  padding: 0px;
}
```

## 5. Layout Principles

- **Base spacing unit:** `12px` — use multiples (24px, 36px, 48px, etc.)

### Spacing Scale (extracted from real elements)

| Token | Value | Role |
|---|---|---|
| spacing-1 | `12px` | element |
| spacing-2 | `8px` | element |
| spacing-3 | `4px` | element |
| spacing-4 | `6px` | element |
| spacing-5 | `20px` | element |
| spacing-6 | `14px` | element |
| spacing-7 | `16px` | element |
| spacing-8 | `10px` | element |

### Border Radius Scale

| Token | Value | Element |
|---|---|---|
| radius-button | `8px` | button |
| radius-card | `20px` | card |
| radius-pill | `100px` | pill |
| radius-button | `6px` | button |
| radius-button | `10px` | button |
| radius-card | `16px` | card |

## 6. Depth & Elevation

| Level | Shadow | Usage |
|---|---|---|
| Mid | `rgba(129, 126, 126, 0.18) 0px 2px 10px 0px` | Dropdowns, popovers |
| High | `rgba(42, 57, 78, 0.12) 0px 0px 24px 0px` | Modals, floating elements |

> **Note:** This site uses chromatic (color-tinted) shadows rather than pure black — this is a deliberate brand choice that adds warmth to elevation.

## 7. Do's and Don'ts

### Do
- Use `#ffffff` as the primary background color
- Use `CircularXXSub-Bold` for all headings and `ui-sans-serif` for body text
- Use `#ef9309` as the single dominant accent/CTA color
- Maintain `12px` as the base spacing unit — all gaps should be multiples
- Use rounded corners (`8px`+) consistently for all interactive elements
- Use serif fonts for headlines to maintain editorial authority
- Embrace bold color combinations — playful energy is the point
- Apply the shadow system for elevation — use the extracted shadow values
- Use weight 400 for headings to match the brand's typographic voice

### Don't
- Don't use colors outside the extracted palette without justification
- Don't substitute CircularXXSub-Bold/ui-sans-serif with generic alternatives
- Don't use irregular spacing — stick to 12px grid
- Don't use dark/black backgrounds — this is a light-themed design
- Don't use sharp corners — they feel hostile in this rounded design language
- Don't mix in geometric sans-serif headlines — it breaks the editorial tone
- Don't use pure black (#000000) for text — use `#000000` instead
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
- Maintain 12px base unit across breakpoints — only scale multipliers

## 9. Agent Prompt Guide

### Quick Color Reference

```
Background:  #ffffff
Text:        #000000
Accent:      #ef9309
Secondary:   #2196d4
Border:      #e5e5e5
```

### Example Prompts

1. "Build a hero section with a `#ffffff` background, `CircularXXSub-Bold` heading in `#000000`, and a `#ef9309` CTA button with 8px radius."
2. "Create a pricing card using background `#000000`, border `#e5e5e5`, `ui-sans-serif` for text, and 36px padding."
3. "Design a navigation bar — `#ffffff` background, `#000000` links, `#ef9309` for active state."
4. "Build a feature grid with 3 columns, 36px gap, each card using the card component style."
5. "Create a footer with `#000000` background, `#ffffff` text, and 24px padding."

### Iteration Guide

1. Start with layout structure (sections, grid, spacing)
2. Apply colors from the palette — background first, then text, then accents
3. Set typography — font families, sizes from the type scale, weights
4. Add components — buttons, cards, inputs using the specs above
5. Apply border-radius consistently across all elements
6. Add shadows for depth — use the extracted shadow values, not defaults
7. Check responsive behavior — test mobile and tablet layouts
8. Final pass — verify all colors match, spacing is consistent, fonts are correct

## 10. CSS Custom Properties

> 15 custom properties extracted from `:root` / `html` stylesheets.

### Color Variables

| Variable | Value |
|---|---|
| `--btn-bg` | `#ef9309` |
| `--btn-border` | `1px solid hsla(0,0%,100%,.5)` |
| `--btn-bg1` | `linear-gradient(180deg,rgba(18,40,55,0) -77.99%,rgba(0,188,205,.5) 116.74%),linear-gradient(180deg,#27fdb1,#006e47)` |
| `--btn-shadow` | `1px 1px 25px 10px hsla(0,0%,100%,.5)` |
| `--shine-color` | `hsla(0,0%,100%,.5)` |
| `--swiper-theme-color` | `#007aff` |

### Spacing Variables

| Variable | Value |
|---|---|
| `--swiper-navigation-size` | `10px` |

### Other Variables

| Variable | Value |
|---|---|
| `--book` | `"CircularXXSub-Book",sans-serif` |
| `--bold` | `"CircularXXSub-Bold",sans-serif` |
| `--medium` | `"CircularXXSub-Medium",sans-serif` |
| `--regular` | `"CircularXXSub-Regular",sans-serif` |
| `--light` | `"CircularXXSub-Light",sans-serif` |
| `--shine-degree` | `120deg` |
| `--shine-effect` | `linear-gradient(var(--shine-degree),transparent,var(--shine-color),transparent)` |
| `--shine-transition` | `all 5s ease-in-out` |
