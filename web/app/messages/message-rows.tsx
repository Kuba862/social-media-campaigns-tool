"use client";

import { useState } from "react";
import { Status } from "@/components/status";
import { eventLabels, messageLabel, metaJson, type MessageRow } from "@/lib/messages";

/** The log's rows; a click on a row (or its disclosure button) opens Meta's raw JSON under it. */
export function MessageRows({ rows }: { rows: MessageRow[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const toggle = (id: string) => setOpen((current) => (current === id ? null : id));
  return (
    <tbody>
      {rows.map((row) => {
        const expanded = open === row.id;
        return [
          <tr key={row.id} className="expandable" onClick={() => toggle(row.id)}>
            <td>
              <button
                type="button"
                className="disclosure"
                aria-expanded={expanded}
                aria-label={expanded ? "Hide Meta JSON" : "Show Meta JSON"}
                onClick={(event) => {
                  event.stopPropagation();
                  toggle(row.id);
                }}
              >
                {expanded ? "▾" : "▸"}
              </button>{" "}
              {row.created_at.slice(0, 19).replace("T", " ")}
            </td>
            <td>{messageLabel(row)}</td>
            <td>{row.contacts?.phone_e164 ?? "-"}</td>
            <td>
              <Status value={row.status} />
            </td>
            <td>{eventLabels(row.message_events).join(", ") || "-"}</td>
            <td>{row.error?.message ?? ""}</td>
          </tr>,
          expanded ? (
            <tr key={`${row.id}-json`} className="detail">
              <td colSpan={6}>
                <pre aria-label="Meta JSON">{metaJson(row)}</pre>
              </td>
            </tr>
          ) : null,
        ];
      })}
    </tbody>
  );
}
