import Link from "next/link";

const LINKS = [
  ["/", "Home"],
  ["/templates", "Templates"],
  ["/messages", "Messages"],
  ["/journeys", "Journeys"],
] as const;

/** The panel's top bar; `current` marks the section, `email` shows who is signed in. */
export function Nav({ current, email }: { current?: string; email?: string }) {
  return (
    <nav className="nav" aria-label="Main">
      <span className="brand">WhatsApp campaigns</span>
      {LINKS.map(([href, label]) => (
        <Link key={href} href={href} aria-current={current === href ? "page" : undefined}>
          {label}
        </Link>
      ))}
      <span className="spacer" />
      {email && <span className="user">{email}</span>}
    </nav>
  );
}
