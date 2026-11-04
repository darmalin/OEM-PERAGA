import { ChevronRight } from "lucide-react";

import { date, type Me, href, navigate } from "../lib";
import { Status } from "../ui";

/** Every edition the account exhibits in; usually one. */
export function Home({ me }: { me: Me }) {
  return (
    <div>
      <h1 className="mb-1 text-[24px] leading-8 font-semibold tracking-[-0.01em]">My Exhibitions</h1>
      <p className="mb-6 text-[14px] text-muted">Open an exhibition to fill in its contract and see your payments.</p>
      {me.exhibitors.length === 0 ? (
        <p className="rounded-[12px] border border-line bg-bg px-5 py-10 text-center text-[14px] text-muted">
          No exhibition is linked to this account. Ask your sales contact if you expected one.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {me.exhibitors.map((e) => {
            const to = `/e/${e.exhibitor_lead_id}`;
            return (
              <li key={e.exhibitor_lead_id}>
                <a
                  href={href(to)}
                  onClick={(ev) => { ev.preventDefault(); navigate(to); }}
                  className="flex items-center gap-4 rounded-[12px] border border-line bg-bg px-5 py-4 hover:bg-subtle max-sm:px-4"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-[16px] font-semibold">{e.edition_name}</span>
                    <span className="block text-[13px] text-muted">
                      {date(e.edition_start_date)} to {date(e.edition_end_date)} · {e.company_name}
                      {e.booth_code ? ` · Booth ${e.booth_code}` : ""}
                    </span>
                    <span className="mt-2 flex flex-wrap gap-2">
                      <Status value={e.contract_status} />
                      <Status value={e.payment_state} />
                    </span>
                  </span>
                  <ChevronRight className="size-5 shrink-0 text-label" aria-hidden />
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
