import type { Schemas } from "@ems/api";

import { formatDateTime, relative } from "@/lib/format";

type Entry = Schemas["AuditLogOut"];

function show(v: unknown): string {
  if (v == null || v === "") return "empty";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "empty";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function humanize(s: string): string {
  return s.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Frappe-style activity: who did what, when; the before/after diff on demand. */
export function ActivityTimeline({ entries, timezone }: { entries: Entry[]; timezone?: string }) {
  return (
    <ol className="relative flex flex-col">
      {entries.map((e) => {
        const keys = Array.from(new Set([...Object.keys(e.before ?? {}), ...Object.keys(e.after ?? {})]));
        return (
          <li key={e.id} className="relative border-l border-line pb-5 pl-5 last:pb-0">
            <span className="absolute top-1.5 -left-[4.5px] size-2 rounded-full bg-[var(--ink-label)]" aria-hidden />
            <p className="text-[13px]">
              <span className="font-medium">{e.actor_name ?? "System"}</span>{" "}
              <span className="text-muted">{humanize(e.action)}</span>{" "}
              <span className="text-label">{humanize(e.entity_type)}</span>
            </p>
            <p className="text-[12px] text-label tabular" title={formatDateTime(e.occurred_at, timezone)}>
              {relative(e.occurred_at)} · {e.source}
            </p>
            {keys.length > 0 ? (
              <details className="mt-1.5 text-[12px]">
                <summary className="cursor-pointer rounded-[4px] text-link select-none">
                  {keys.length} {keys.length === 1 ? "field" : "fields"}
                </summary>
                <dl className="mt-2 grid grid-cols-[minmax(0,140px)_minmax(0,1fr)] gap-x-3 gap-y-1">
                  {keys.map((k) => (
                    <div key={k} className="contents">
                      <dt className="text-label">{humanize(k)}</dt>
                      <dd className="break-words">
                        {e.before && k in e.before ? (
                          <>
                            <span className="text-muted line-through">{show(e.before[k])}</span>
                            <span className="text-label"> to </span>
                          </>
                        ) : null}
                        <span>{show(e.after?.[k])}</span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </details>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
