# Design System Inspired by TradeMentor

> Auto-extracted from `https://id-preview--36d73b9c-8b29-4ff1-a7ad-9be86596f341.lovable.app/` on 2026-06-14

## 1. Visual Theme & Atmosphere

Energetic and playful with bold colors and confident hierarchy.

The hero section leads with "You don't have astrategy problem.You have a 7-second problem." followed by "The seven seconds between getting stopped out and clicking buy again. That's where the month dies — ".

**Key Characteristics:**
- Geist as the heading font
- Inter as the body font for all running text
- Heading weight 600, letter-spacing -1.6px
- Light/white background (#f5f6f9) as the primary canvas
- Primary accent `#f0a119` used for CTAs and brand highlights
- 6 shadow level(s) detected — tinted shadows
- Rounded corners (14px+) creating a friendly, approachable feel
- Tags: light, rounded, colorful, monospace, sans-serif

## 2. Color Palette & Roles

### Primary
- **Primary Accent** (`#f0a119`) · `--color-primary`: Brand color, CTA backgrounds, link text, interactive highlights.
- **Secondary Accent** (`#3e51cc`) · `--color-secondary`: Secondary brand, hover states, complementary highlights.
- **Background** (`#f5f6f9`) · `--color-bg`: Page background, primary canvas.

### Text
- **Text Primary** (`#1d2334`) · `--color-text`: Headings and body text.
- **Text Secondary** (`#676e83`) · `--color-text-secondary`: Muted text, captions, placeholders.

### Borders & Surfaces
- **Border** (`#edeef3`) · `--color-border`: Dividers, outlines, input borders.

### Full Extracted Palette

| # | Hex | CSS Variable | Role | Area | Contrast |
|---|---|---|---|---|---|
| 1 | `#ffffff` | `--palette-1` | section | large | text-dark |
| 2 | `#f5f6f9` | `--palette-2` | block | large | text-dark |
| 3 | `#edeef3` | `--palette-3` | block | large | text-dark |
| 4 | `#faf0ef` | `--palette-4` | block | large | text-dark |
| 5 | `#3e51cc` | `--palette-5` | badge | medium | text-light |
| 6 | `#df5349` | `--palette-6` | text-accent | medium | text-light |
| 7 | `#1d2334` | `--palette-7` | button | medium | text-light |
| 8 | `#676e83` | `--palette-8` | text-accent | small | text-light |
| 9 | `#1b1b1b` | `--palette-9` | button | small | text-light |
| 10 | `#f0a119` | `--palette-10` | text-accent | small | text-dark |
| 11 | `#33a36f` | `--palette-11` | text-accent | small | text-light |

## 3. Typography Rules

- **Heading Font:** `Geist`, sans-serif
- **Body Font:** `Inter`, sans-serif

### Type Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|---|---|---|---|---|---|
| H1 | Geist | 64px | 600 | 65.28px | -1.6px |
| H2 | Geist | 44px | 600 | 46.2px | -1.1px |
| H3 | Geist | 16px | 400 | 24px | -0.32px |
| Body | Inter | 18px | 400 | 27.9px | normal |
| Small | Inter | 14px | 600 | 20px | normal |
| Code | Geist Mono | 14px | 400 | 21px | normal |

### Type Scale

| Token | Size | Suggested Usage |
|---|---|---|
| Display | `88px` | headings |
| H1 | `64px` | headings |
| H2 | `56px` | headings |
| H3 | `48px` | headings |
| H4 | `44px` | headings |
| Body L | `40px` | body / supporting text |
| Body | `28px` | body / supporting text |
| Small | `24px` | body / supporting text |
| XS | `20px` | body / supporting text |
| Caption | `19px` | body / supporting text |

## 4. Component Stylings

### Primary Button

```css
.btn-primary {
  background: transparent;
  color: #676e83;
  border-radius: 12px;
  padding: 0px 0px;
  font-size: 16px;
  font-weight: 400;
  border: none;
  cursor: pointer;
}
```

### Filled Button

```css
.btn-filled {
  background: #3e51cc;
  color: #ffffff;
  border-radius: 14px;
  padding: 0px 16px;
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
}
```

### Filled Button 2

```css
.btn-filled-2 {
  background: #f5f6f9;
  color: #1d2334;
  border-radius: 14px;
  padding: 8px 24px;
  font-size: 14.5px;
  font-weight: 600;
  border: none;
  cursor: pointer;
}
```

### Filled Button 3

```css
.btn-filled-3 {
  background: #ffffff;
  color: #1d2334;
  border-radius: 14px;
  padding: 0px 16px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid rgb(224, 226, 235);
  cursor: pointer;
}
```

### Filled Button 4

```css
.btn-filled-4 {
  background: #ffffff;
  color: #676e83;
  border-radius: 14px;
  padding: 0px 16px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid rgb(224, 226, 235);
  cursor: pointer;
}
```

### Pill Button

```css
.btn-pill {
  background: #3e51cc;
  color: #3e51cc;
  border-radius: 9999px;
  padding: 0px 0px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  cursor: pointer;
}
```

### Card

```css
.card {
  background: #ffffff;
  border-radius: 16px;
  padding: 0px;
  box-shadow: rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(55, 65, 98, 0.25) 0px 30px 80px -30px;
}
```

## 5. Layout Principles

- **Base spacing unit:** `8px` — use multiples (16px, 24px, 32px, etc.)

### Spacing Scale (extracted from real elements)

| Token | Value | Role |
|---|---|---|
| spacing-1 | `8px` | element |
| spacing-2 | `20px` | element |
| spacing-3 | `112px` | section |
| spacing-4 | `16px` | element |
| spacing-5 | `10px` | element |
| spacing-6 | `12px` | element |
| spacing-7 | `2px` | element |
| spacing-8 | `4px` | element |

### Border Radius Scale

| Token | Value | Element |
|---|---|---|
| radius-button | `14px` | button |
| radius-button | `12px` | button |
| radius-subtle | `2px` | subtle |
| radius-subtle | `3px` | subtle |
| radius-card | `16px` | card |
| radius-button | `6px` | button |

## 6. Depth & Elevation

| Level | Shadow | Usage |
|---|---|---|
| Low | `rgba(18, 21, 33, 0.04) 0px 1px 2px 0px, rgba(18, 21, 33, 0.18) 0px 12px 32px -12...` | Cards, subtle elevation |
| Low | `rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0...` | Cards, subtle elevation |
| Low | `rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(55, 65,...` | Cards, subtle elevation |
| Low | `rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(223, 83...` | Cards, subtle elevation |
| Low | `rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(55, 65,...` | Cards, subtle elevation |

> **Note:** This site uses chromatic (color-tinted) shadows rather than pure black — this is a deliberate brand choice that adds warmth to elevation.

## 7. Do's and Don'ts

### Do
- Use `#f5f6f9` as the primary background color
- Use `Geist` for all headings and `Inter` for body text
- Use `#f0a119` as the single dominant accent/CTA color
- Maintain `8px` as the base spacing unit — all gaps should be multiples
- Use rounded corners (`14px`+) consistently for all interactive elements
- Embrace bold color combinations — playful energy is the point
- Apply the shadow system for elevation — use the extracted shadow values
- Use weight 600 for headings to match the brand's typographic voice

### Don't
- Don't use colors outside the extracted palette without justification
- Don't substitute Geist/Inter with generic alternatives
- Don't use irregular spacing — stick to 8px grid
- Don't use dark/black backgrounds — this is a light-themed design
- Don't use sharp corners — they feel hostile in this rounded design language
- Don't use pure black (#000000) for text — use `#1d2334` instead
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
- Maintain 8px base unit across breakpoints — only scale multipliers

## 9. Agent Prompt Guide

### Quick Color Reference

```
Background:  #f5f6f9
Text:        #1d2334
Accent:      #f0a119
Secondary:   #3e51cc
Border:      #edeef3
```

### Example Prompts

1. "Build a hero section with a `#f5f6f9` background, `Geist` heading in `#1d2334`, and a `#f0a119` CTA button with 14px radius."
2. "Create a pricing card using background `#f5f6f9`, border `#edeef3`, `Inter` for text, and 24px padding."
3. "Design a navigation bar — `#f5f6f9` background, `#1d2334` links, `#f0a119` for active state."
4. "Build a feature grid with 3 columns, 24px gap, each card using the card component style."
5. "Create a footer with `#1d2334` background, `#f5f6f9` text, and 16px padding."

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

> 42 custom properties extracted from `:root` / `html` stylesheets.

### Color Variables

| Variable | Value |
|---|---|
| `--shadow-clay` | `-2px -2px 6px hsl(var(--clay-light) / .7), 4px 6px 16px hsl(var(--clay-dark) / .14)` |
| `--shadow-clay-sm` | `-1px -1px 3px hsl(var(--clay-light) / .6), 2px 3px 8px hsl(var(--clay-dark) / .1)` |
| `--shadow-clay-inset` | `inset 2px 2px 5px hsl(var(--clay-dark) / .12), inset -1px -1px 3px hsl(var(--clay-light) / .6)` |
| `--shadow-clay-hover` | `-2px -2px 6px hsl(var(--clay-light) / .7), 6px 8px 20px hsl(var(--clay-dark) / .18)` |

### Spacing Variables

| Variable | Value |
|---|---|
| `--radius` | `.875rem` |

### Other Variables

| Variable | Value |
|---|---|
| `--background` | `230 25% 97%` |
| `--foreground` | `226 28% 16%` |
| `--card` | `0 0% 100%` |
| `--card-foreground` | `226 28% 16%` |
| `--popover` | `0 0% 100%` |
| `--popover-foreground` | `226 28% 16%` |
| `--primary` | `232 58% 52%` |
| `--primary-foreground` | `0 0% 100%` |
| `--secondary` | `230 20% 94%` |
| `--secondary-foreground` | `226 28% 16%` |
| `--muted` | `230 20% 94%` |
| `--muted-foreground` | `226 12% 46%` |
| `--accent` | `232 58% 52%` |
| `--accent-foreground` | `0 0% 100%` |
| `--destructive` | `4 70% 58%` |
| ... | *(22 more)* |
