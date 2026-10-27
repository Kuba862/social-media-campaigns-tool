import type { PreviewSegment } from "@/lib/template-rules";

export type PreviewButton = { type: "quick_reply" | "url"; text: string };

/**
 * A message as the contact will see it: the WhatsApp bubble with an optional header (text or
 * image), the body with example values in place of variables, a footer and the buttons.
 */
export function MessagePreview({
  title,
  header,
  image,
  body,
  footer,
  buttons = [],
}: {
  title: string;
  header?: string | null;
  image?: string | null;
  body: PreviewSegment[];
  footer?: string | null;
  buttons?: PreviewButton[];
}) {
  const empty = body.every((segment) => segment.text.trim() === "") && !image && !header;
  return (
    <figure className="wa-chat" aria-label={title}>
      <div className="wa-bubble">
        {image && (
          <div className="wa-image">
            {/* eslint-disable-next-line @next/next/no-img-element -- a preview of a user-typed https address */}
            <img src={image} alt="" referrerPolicy="no-referrer" />
          </div>
        )}
        {header && <p className="wa-header">{header}</p>}
        <p className="wa-body">
          {empty && <span className="wa-placeholder">The message appears here as you type.</span>}
          {body.map((segment, index) =>
            segment.variable ? (
              <mark key={index} title={`variable {{${segment.variable}}}`}>
                {segment.text}
              </mark>
            ) : (
              <span key={index}>{segment.text}</span>
            ),
          )}
        </p>
        {footer && <p className="wa-footer">{footer}</p>}
        <span className="wa-time">12:00</span>
      </div>
      {buttons.filter((button) => button.text.trim() !== "").length > 0 && (
        <ul className="wa-buttons">
          {buttons
            .filter((button) => button.text.trim() !== "")
            .map((button, index) => (
              <li key={index}>
                <span aria-hidden="true">{button.type === "url" ? "↗" : "↩"}</span> {button.text}
              </li>
            ))}
        </ul>
      )}
    </figure>
  );
}
