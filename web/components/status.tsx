/** A status pill; the colour comes from the value itself (see .badge[data-status] in CSS). */
export function Status({ value }: { value: string }) {
  return (
    <span className="badge" data-status={value}>
      {value}
    </span>
  );
}
