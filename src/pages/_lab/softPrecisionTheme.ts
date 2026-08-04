/**
 * Soft Precision — one palette, shared by the mobile and desktop studies.
 *
 * THE PROBLEM THIS SOLVES. The first pass carried four hues — indigo, green, red,
 * amber — and several of them were doing more than one job:
 *
 *   green   profit  AND  "Connected"  AND  "Guardian Active"  AND  a toggle that is on
 *   red     loss    AND  high severity  AND  the danger button
 *   amber   medium severity  AND  the broker icon
 *   indigo  brand   AND  active nav  AND  the AI coach
 *
 * A colour that means several things means nothing. Reading a screen became a
 * lookup rather than a glance, which is what "too many colours" actually is.
 *
 * THE RULE. Three hues, one job each:
 *
 *   ACCENT (indigo)   everything that is not money. Brand, navigation, active
 *                     states, the coach, "connected", "on", a good day.
 *   UP (green)        money gained. NOTHING ELSE. This is the important one — the
 *                     moment green also means "fine", a trader can no longer find
 *                     their P&L by colour alone.
 *   DOWN (red)        money lost, and risk. Severity is three STRENGTHS of this
 *                     one hue — solid, tint, neutral — instead of a third colour.
 *
 * Amber is gone entirely. It only ever existed to sit between red and grey, and a
 * lighter red does that without adding a hue.
 *
 * Both greens and reds are also deeper and less saturated than the first pass.
 * The originals (#10B981 / #F4425F) are near-neon; against a white card at 26px
 * they shout. These sit back far enough to read as instrumentation.
 */

export const T = {
  // Neutrals — a cool grey ground so the accent stays the only warm-ish thing.
  ground: '#F6F7F9',
  surface: '#FFFFFF',
  ink: '#1F2333',
  body: '#565C6E',
  muted: '#9096A6',
  faint: '#C2C7D2',
  line: '#E8EAEF',

  // ACCENT — everything that is not money.
  accent: '#4A46D6',
  accentTint: '#EEEDFB',
  accentDeep: '#3A36B8',

  // UP — money gained. Only ever money.
  up: '#0F9D76',
  upTint: '#E6F4EF',

  // DOWN — money lost, and risk. Severity is strengths of this, not a new hue.
  down: '#D42F4E',
  downTint: '#FBE9ED',

  neutralTint: '#F1F2F6',
} as const;

export type Tone = 'accent' | 'up' | 'down' | 'neutral';

/** [tint, full] for a tone. Used by every pill, chip and icon tile. */
export const TONE: Record<Tone, readonly [string, string]> = {
  accent:  [T.accentTint, T.accent],
  up:      [T.upTint, T.up],
  down:    [T.downTint, T.down],
  neutral: [T.neutralTint, T.muted],
};

/**
 * Severity without a third hue. High shouts, medium states, low recedes —
 * all from the same red, which is why three levels do not read as three topics.
 */
export const SEVERITY: Record<'high' | 'med' | 'low', Tone> = {
  high: 'down',
  med: 'down',
  low: 'neutral',
};

export const CARD: React.CSSProperties = {
  background: T.surface,
  borderRadius: 20,
  boxShadow: '0 4px 24px rgba(31,35,51,0.06)',
};

export const FONT = "'Poppins', 'Geist', system-ui, sans-serif";
