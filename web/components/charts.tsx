/**
 * Small SVG charts for the home page, rendered on the server. One hue per chart (two for the
 * stacked sync columns), thin marks with a rounded data end, a 2px surface gap between fills,
 * native <title> tooltips on hit areas larger than the marks, and a table twin under each chart.
 */
import type { ReactNode } from "react";

export type ColumnPoint = { label: string; values: number[]; title: string };
export type BarRow = { label: string; value: number };

const WIDTH = 320;

/** A column with a 4px rounded top and a square baseline; `top` is the y of its upper edge. */
function columnPath(x: number, top: number, width: number, height: number): string {
  const r = Math.min(4, width / 2, height);
  return [
    `M${x} ${top + height}`,
    `V${top + r}`,
    `q0 ${-r} ${r} ${-r}`,
    `h${width - 2 * r}`,
    `q${r} 0 ${r} ${r}`,
    `V${top + height}`,
    "Z",
  ].join(" ");
}

/** A horizontal bar with a 4px rounded right end and a square left end at the axis. */
function barPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(4, height / 2, width);
  return [
    `M${x} ${y}`,
    `h${width - r}`,
    `q${r} 0 ${r} ${r}`,
    `v${height - 2 * r}`,
    `q0 ${r} ${-r} ${r}`,
    `H${x}`,
    "Z",
  ].join(" ");
}

function hasData(values: number[]): boolean {
  return values.some((value) => value > 0);
}

/** Vertical columns over a sequence (days, runs); up to two stacked series, 2px gap between. */
export function Columns({
  points,
  series,
  title,
}: {
  points: ColumnPoint[];
  series: string[];
  title: string;
}) {
  const height = 150;
  const top = 18;
  const baseline = 116;
  const plot = baseline - top;
  const max = Math.max(1, ...points.map((point) => point.values.reduce((a, b) => a + b, 0)));
  const slot = WIDTH / Math.max(points.length, 1);
  const width = Math.min(24, Math.max(4, slot - 4));
  const peak = points.reduce(
    (best, point, index) => {
      const total = point.values.reduce((a, b) => a + b, 0);
      return total > best.total ? { total, index } : best;
    },
    { total: 0, index: -1 },
  );
  if (!hasData(points.flatMap((point) => point.values))) return <Empty />;
  return (
    <svg className="viz" viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={title}>
      <line className="axis" x1={0} x2={WIDTH} y1={baseline + 0.5} y2={baseline + 0.5} />
      {points.map((point, index) => {
        const x = index * slot + (slot - width) / 2;
        let y = baseline;
        const segments = point.values.map((value, s) => {
          const h = (value / max) * plot;
          const gap = s > 0 && value > 0 ? 2 : 0;
          const segmentTop = y - h;
          y = segmentTop - gap;
          return value > 0 ? (
            <path
              key={s}
              className={s === 0 ? "mark" : "mark-2"}
              d={columnPath(x, segmentTop, width, Math.max(h - gap, 0))}
            />
          ) : null;
        });
        const total = point.values.reduce((a, b) => a + b, 0);
        return (
          <g key={`${index}-${point.label}`}>
            <title>{point.title}</title>
            <rect className="hit" x={index * slot} y={0} width={slot} height={height} />
            {segments}
            {index === peak.index && total > 0 && (
              <text
                className="label"
                x={x + width / 2}
                y={baseline - (total / max) * plot - 6}
                textAnchor="middle"
              >
                {total}
              </text>
            )}
          </g>
        );
      })}
      {points.length > 0 && (
        <>
          <text x={0} y={height - 4}>
            {points[0]?.label}
          </text>
          <text x={WIDTH} y={height - 4} textAnchor="end">
            {points.at(-1)?.label}
          </text>
        </>
      )}
      {series.length > 1 && <desc>{`Series: ${series.join(", ")}`}</desc>}
    </svg>
  );
}

/** Horizontal bars for a handful of categories, value at the tip of every bar. */
export function Bars({ rows, title }: { rows: BarRow[]; title: string }) {
  const rowHeight = 26;
  const labelWidth = 118;
  const height = rows.length * rowHeight + 4;
  const max = Math.max(1, ...rows.map((row) => row.value));
  const span = WIDTH - labelWidth - 36;
  if (!hasData(rows.map((row) => row.value))) return <Empty />;
  return (
    <svg className="viz" viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={title}>
      {rows.map((row, index) => {
        const y = index * rowHeight + 2;
        const width = Math.max(2, (row.value / max) * span);
        return (
          <g key={row.label}>
            <title>{`${row.label}: ${row.value}`}</title>
            <rect className="hit" x={0} y={y} width={WIDTH} height={rowHeight} />
            <text x={labelWidth - 8} y={y + 16} textAnchor="end">
              {row.label}
            </text>
            <path className="mark" d={barPath(labelWidth, y + 4, width, 16)} />
            <text className="label" x={labelWidth + width + 6} y={y + 16}>
              {row.value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Empty() {
  return <p className="empty viz-empty">No data yet.</p>;
}

/** The legend for charts with more than one series; a single series needs none. */
export function Legend({ series }: { series: string[] }) {
  if (series.length < 2) return null;
  return (
    <ul className="legend" aria-label="Series">
      {series.map((name, index) => (
        <li key={name}>
          <i className={index === 0 ? "mark" : "mark-2"} aria-hidden="true" />
          {name}
        </li>
      ))}
    </ul>
  );
}

/** The table twin of a chart: the same numbers, readable without colour or hover. */
export function DataTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <details className="viz-table">
      <summary>Table</summary>
      <table>
        <thead>
          <tr>
            {head.map((cell) => (
              <th key={cell}>{cell}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, c) => (
                <td key={c}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** One box of the 2x2 grid: a stat tile on top, the chart under it. */
export function StatCard({
  id,
  title,
  value,
  note,
  children,
}: {
  id: string;
  title: string;
  value: string | number;
  note: string;
  children: ReactNode;
}) {
  return (
    <section className="card stat" aria-labelledby={`stat-${id}`}>
      <h2 id={`stat-${id}`}>{title}</h2>
      <p className="value">{value}</p>
      <p className="note">{note}</p>
      {children}
    </section>
  );
}
