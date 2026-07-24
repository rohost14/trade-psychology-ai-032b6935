/**
 * Single source for the support/contact channel surfaced in error UIs.
 * Change SUPPORT_EMAIL here to reroute every "Contact support" link in the app.
 */
export const SUPPORT_EMAIL = 'support@tradementor.ai';

/** Build a mailto: link, optionally prefilled with an error reference so the user's
 *  email arrives with the Sentry id we can look up. */
export function supportMailto(opts?: { subject?: string; ref?: string }): string {
  const subject = encodeURIComponent(opts?.subject || 'TradeMentor — I need help');
  const bodyParts: string[] = [];
  if (opts?.ref) bodyParts.push(`\n\n\n---\nError reference: ${opts.ref}`);
  const body = bodyParts.length ? `&body=${encodeURIComponent(bodyParts.join(''))}` : '';
  return `mailto:${SUPPORT_EMAIL}?subject=${subject}${body}`;
}
