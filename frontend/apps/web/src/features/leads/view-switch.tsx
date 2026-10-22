import { Link } from "@tanstack/react-router";
import { Columns3, List } from "lucide-react";

import { cn } from "@/lib/cn";

/** List / Board switch on the Visitor Leads pages (Frappe's view switcher). */
export function LeadViewSwitch({ current }: { current: "list" | "board" }) {
  const item = "flex h-7 items-center gap-1.5 rounded-[6px] px-2.5 text-[13px] text-label hover:text-ink pointer-coarse:h-10";
  const on = "bg-bg text-ink shadow-[0_1px_2px_rgb(0_0_0/0.08)]";
  return (
    <div className="flex gap-1 rounded-[8px] bg-input p-1" role="group" aria-label="View">
      <Link to="/app/visitor-leads" aria-current={current === "list" ? "page" : undefined} className={cn(item, current === "list" && on)}>
        <List className="size-4" aria-hidden />List
      </Link>
      <Link to="/app/visitor-leads/board" aria-current={current === "board" ? "page" : undefined} className={cn(item, current === "board" && on)}>
        <Columns3 className="size-4" aria-hidden />Board
      </Link>
    </div>
  );
}
