import { ArrowRight, CalendarDays } from "lucide-react";

import { date, type Me, href, navigate, showCountdown } from "../lib";
import { BoothTag, Status } from "../ui";

/** Every edition the account exhibits in; usually one, so each gets a full-width card. */
export function Home({ me }: { me: Me }) {
  const company = me.exhibitors[0]?.company_name;
  return (
    <div className="flex flex-col gap-6">
      <div>
        {company ? <p className="text-[15px] font-semibold text-primary">Hello, {company}</p> : null}
        <h1 className="mt-1 text-[30px] leading-tight font-extrabold text-ink max-sm:text-[26px]">My Exhibitions</h1>
        <p className="mt-1 text-[15px] text-muted">Open an exhibition to sign the contract, order services for your booth, and follow your payments.</p>
      </div>
      {me.exhibitors.length === 0 ? (
        <p className="rounded-[16px] border border-line bg-bg px-6 py-10 text-center text-[15px] text-muted">
          No exhibition is linked to this account yet. Ask your sales contact at PERAGA Expo if you expected one.
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {me.exhibitors.map((e) => {
            const to = `/e/${e.exhibitor_lead_id}`;
            const when = showCountdown(e.edition_start_date, e.edition_end_date);
            return (
              <li key={e.exhibitor_lead_id}>
                <a
                  href={href(to)}
                  onClick={(ev) => { ev.preventDefault(); navigate(to); }}
                  className="group grid overflow-hidden rounded-[16px] border border-line bg-bg transition-colors hover:border-primary/40 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]"
                >
                  <div className="flex items-start justify-between gap-4 bg-primary px-6 py-5 text-on-primary max-sm:px-4">
                    <div className="min-w-0">
                      <p className="flex items-center gap-1.5 text-[13px] font-semibold text-hero-muted">
                        <CalendarDays className="size-4" aria-hidden />{date(e.edition_start_date)} to {date(e.edition_end_date)}
                      </p>
                      <p className="mt-1 font-display text-[22px] leading-tight font-extrabold">{e.edition_name}</p>
                      <p className={when.live ? "mt-3 inline-flex rounded-full bg-accent px-3 py-1 text-[13px] font-bold" : "mt-3 inline-flex rounded-full bg-bg/15 px-3 py-1 text-[13px] font-semibold"}>{when.text}</p>
                    </div>
                    <BoothTag code={e.booth_code} inverse />
                  </div>
                  <div className="flex flex-col justify-between gap-4 px-6 py-5 max-sm:px-4">
                    <dl className="flex flex-col gap-2.5 text-[14px]">
                      <div className="flex items-center justify-between gap-3">
                        <dt className="text-muted">Contract</dt>
                        <dd>{e.contract_status ? <Status value={e.contract_status} /> : <span className="text-label">Not created yet</span>}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt className="text-muted">Booth payment</dt>
                        <dd>{e.payment_state ? <Status value={e.payment_state} /> : <span className="text-label">After signing</span>}</dd>
                      </div>
                    </dl>
                    <span className="inline-flex items-center gap-1.5 self-end text-[15px] font-semibold text-primary group-hover:underline">
                      Open exhibition<ArrowRight className="size-4" aria-hidden />
                    </span>
                  </div>
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
