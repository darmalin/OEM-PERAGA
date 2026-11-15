import { CalendarDays, ChevronRight, MapPin } from "lucide-react";

import { brandOf, date, href, type Me, navigate, showCountdown } from "../lib";
import { PageBody, PageHead, Status } from "../ui";

/** Every edition the account exhibits in; usually one. Each card carries its show's logo. */
export function Home({ me }: { me: Me }) {
  const company = me.exhibitors[0]?.company_name;
  return (
    <>
      <PageHead title="My Exhibitions" subtitle={company ? `${company} · PERAGA Expo Online Exhibitor Manual` : "PERAGA Expo Online Exhibitor Manual"} />
      <PageBody className="max-w-[1080px]">
        {me.exhibitors.length === 0 ? (
          <p className="rounded-[12px] border border-line bg-bg px-6 py-10 text-center text-[15px] text-muted">
            No exhibition is linked to this account yet. Ask your sales contact at PERAGA Expo if you expected one.
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {me.exhibitors.map((e) => {
              const to = `/e/${e.exhibitor_lead_id}`;
              const when = showCountdown(e.edition_start_date, e.edition_end_date);
              const brand = brandOf(e);
              return (
                <li key={e.exhibitor_lead_id} data-theme={brand.theme}>
                  <a href={href(to)} onClick={(ev) => { ev.preventDefault(); navigate(to); }}
                    className="group flex flex-wrap items-center gap-x-6 gap-y-4 rounded-[12px] border border-line bg-bg px-6 py-5 transition-colors hover:border-line-strong max-sm:px-4">
                    <img src={brand.logo.src} alt={brand.logo.alt} width={brand.logo.width} height={brand.logo.height} className="h-9 w-auto" />
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="text-[19px] font-bold text-ink group-hover:underline">{e.edition_name}</span>
                      <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px] text-muted">
                        <span className="flex items-center gap-1.5"><CalendarDays className="size-4" aria-hidden />{date(e.edition_start_date)} to {date(e.edition_end_date)} · {when.text}</span>
                        {e.venue_name ? <span className="flex items-center gap-1.5"><MapPin className="size-4" aria-hidden />{e.venue_name}</span> : null}
                      </span>
                    </span>
                    <span className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[14px]">
                      <span>Booth <span className="font-bold">{e.booth_code ?? "not assigned"}</span></span>
                      <span className="flex items-center gap-2">Contract {e.contract_status ? <Status value={e.contract_status} /> : <span className="text-label">not created yet</span>}</span>
                      <ChevronRight className="size-5 text-ink" aria-hidden />
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
        )}
      </PageBody>
    </>
  );
}
