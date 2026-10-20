/** Is this e-mail inside the allowed panel domain? Case-insensitive, no e-mail means no. */
export function isAllowedEmail(email: string | null | undefined, allowedDomain: string): boolean {
  if (!email || !allowedDomain) return false;

  const domain = email.split("@").pop()?.toLowerCase();
  return domain === allowedDomain.toLowerCase();
}
