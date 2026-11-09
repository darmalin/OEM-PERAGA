import { Indicator } from "@/ui/indicator";

import { ORDER_STATUSES, type StaffOrderRow } from "./queries";

/** Status plus what blocks the review: extra items to price, unsigned contract, moved booth. */
export function OrderFlags({ order: o }: { order: StaffOrderRow }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      <Indicator value={o.status} text={ORDER_STATUSES[o.status as keyof typeof ORDER_STATUSES] ?? o.status} />
      {o.status === "SUBMITTED" && o.unpriced_lines ? <Indicator value="PENDING" text={`${o.unpriced_lines} to price`} /> : null}
      {o.waiting_for_contract ? <Indicator value="DRAFT" text="Contract not signed" /> : null}
      {o.booth_changed && (o.status === "SUBMITTED" || o.status === "RETURNED") ? <Indicator value="PENDING" text="Booth changed" /> : null}
    </span>
  );
}
