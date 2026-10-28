import type { Schemas } from "@ems/api";
import type { ReactNode } from "react";

import { eventCountdown, formatDate } from "@/lib/format";
import { label } from "@/lib/labels";

/** The ink edition band: the single bold accent of ENERGY 2 (DESIGN.md). */
export function EditionBand({
  edition,
  children,
}: {
  edition: Schemas["EditionBrief"];
  children?: ReactNode;
}) {
  return (
    <section className="brand-edition-band relative overflow-hidden rounded-[12px] bg-band px-7 py-6 text-on-band max-md:px-5">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <p className="text-[13px] text-on-band-muted tabular">
            {edition.code} · {label("edition_status", edition.status)} · {edition.timezone}
          </p>
          <h1 className="mt-1 text-[28px] leading-9 font-semibold tracking-[-0.015em] break-words">{edition.name}</h1>
          <p className="mt-1 text-[14px] text-on-band-muted tabular">
            {formatDate(edition.start_date)} to {formatDate(edition.end_date)}
          </p>
        </div>
        <p className="text-[20px] font-semibold tabular">
          {eventCountdown(edition.start_date, edition.end_date, edition.timezone)}
        </p>
      </div>
      {children ? <div className="mt-6">{children}</div> : null}
    </section>
  );
}
