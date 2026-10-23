import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { formatNumber } from "@/lib/format";

import { dayLabel, type Metric, type Row } from "./metrics";

const SERIES: { key: Metric; label: string; color: string }[] = [
  { key: "answer", label: "Answer", color: "var(--series-1)" },
  { key: "non_answer", label: "Non Answer", color: "var(--series-2)" },
  { key: "recontacted", label: "Recontacted", color: "var(--series-3)" },
  { key: "retry_no_answer", label: "Retry No Answer", color: "var(--series-4)" },
];
const H = 260;
const M = { top: 12, right: 120, bottom: 28, left: 44 };

/** Four even steps of 1, 2, or 5 times a power of ten, covering `v`. */
function niceStep(v: number): number {
  const raw = Math.max(v, 4) / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  return ([1, 2, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
}

/** Calls per day: one line per call outcome, crosshair tooltip, direct labels at the end. */
export function TrendChart({ days, byDay }: { days: string[]; byDay: Map<string, Row> }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => entry && setWidth(Math.max(320, entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const value = (i: number, k: Metric) => byDay.get(days[i]!)?.[k] ?? 0;
  const step = niceStep(Math.max(0, ...days.flatMap((_, i) => SERIES.map((s) => value(i, s.key)))));
  const max = step * 4;
  const plotW = width - M.left - M.right;
  const plotH = H - M.top - M.bottom;
  const x = (i: number) => M.left + (days.length < 2 ? plotW / 2 : (i / (days.length - 1)) * plotW);
  const y = (v: number) => M.top + plotH - (v / max) * plotH;
  const ticks = [0, 1, 2, 3, 4].map((t) => t * step);
  const every = Math.max(1, Math.ceil(days.length / Math.max(2, Math.floor(plotW / 70))));

  // Direct labels at the last point, pushed apart so they never overlap.
  const last = days.length - 1;
  const ends = SERIES.map((s) => ({ ...s, y: y(value(last, s.key)) })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) ends[i]!.y = Math.max(ends[i]!.y, ends[i - 1]!.y + 14);

  const pick = (clientX: number) => {
    const rect = box.current?.getBoundingClientRect();
    if (!rect || days.length === 0) return;
    const px = clientX - rect.left - M.left;
    setHover(Math.min(last, Math.max(0, Math.round((px / plotW) * Math.max(1, last)))));
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") setHover((h) => Math.min(last, (h ?? -1) + 1));
    else if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? last + 1) - 1));
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  return (
    <div ref={box} className="relative">
      <svg
        width={width}
        height={H}
        role="img"
        tabIndex={0}
        aria-label={`Calls per day from ${days[0] ? dayLabel(days[0]) : ""} to ${days[last] ? dayLabel(days[last]) : ""}. Use the left and right arrow keys to read each day.`}
        className="block rounded-[8px] outline-offset-2"
        onPointerMove={(e) => pick(e.clientX)}
        onPointerLeave={() => setHover(null)}
        onKeyDown={onKey}
        onBlur={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={M.left + plotW} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth={1} />
            <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-[var(--ink-label)] text-[11px] tabular">{formatNumber(t)}</text>
          </g>
        ))}
        {days.map((d, i) =>
          i % every === 0 || i === last ? (
            <text key={d} x={x(i)} y={H - 8} textAnchor={i === last && i > 0 ? "end" : "middle"} className="fill-[var(--ink-label)] text-[11px]">
              {dayLabel(d).replace(/ \(.*\)/, "")}
            </text>
          ) : null,
        )}
        {SERIES.map((s) => (
          <polyline
            key={s.key}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            points={days.map((_, i) => `${x(i)},${y(value(i, s.key))}`).join(" ")}
          />
        ))}
        {ends.map((s) => (
          <text key={s.key} x={M.left + plotW + 8} y={s.y} dy="0.32em" className="fill-[var(--ink-muted)] text-[11px]">
            {s.label}
          </text>
        ))}
        {hover !== null ? (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + plotH} stroke="var(--ink-label)" strokeWidth={1} />
            {SERIES.map((s) => (
              <circle key={s.key} cx={x(hover)} cy={y(value(hover, s.key))} r={4} fill={s.color} stroke="var(--bg)" strokeWidth={2} />
            ))}
          </g>
        ) : null}
      </svg>
      {hover !== null && days[hover] ? (
        <div
          role="status"
          className="pointer-events-none absolute top-2 z-10 min-w-[170px] rounded-[8px] border border-line bg-bg px-3 py-2 text-[12px] shadow-overlay"
          style={x(hover) > width / 2 ? { right: width - x(hover) + 12 } : { left: x(hover) + 12 }}
        >
          <p className="mb-1 text-label">{dayLabel(days[hover])}</p>
          {SERIES.map((s) => (
            <p key={s.key} className="flex items-center gap-2">
              <span aria-hidden className="h-0.5 w-3 rounded-full" style={{ background: s.color }} />
              <span className="font-semibold tabular">{formatNumber(value(hover, s.key))}</span>
              <span className="text-label">{s.label}</span>
            </p>
          ))}
        </div>
      ) : null}
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-muted" aria-label="Legend">
        {SERIES.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <span aria-hidden className="h-0.5 w-4 rounded-full" style={{ background: s.color }} />
            {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
