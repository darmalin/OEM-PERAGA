import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useEdition } from "@/lib/edition";
import { formatDateTime } from "@/lib/format";
import { options } from "@/lib/labels";
import { FilterBar, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const BUCKETS = ["today", "overdue", "upcoming", "all"] as const;

export const Route = createFileRoute("/app/followups/")({
  validateSearch: z.object({
    bucket: z.enum(BUCKETS).default("today"),
    status: z.enum(["OPEN", "DONE", "CANCELLED"]).default("OPEN"),
    page: z.number().int().min(1).default(1),
    page_size: z.number().int().default(20),
  }),
  component: Followups,
});

const EMPTY: Record<(typeof BUCKETS)[number], string> = {
  today: "Nothing due today.",
  overdue: "No overdue follow-ups.",
  upcoming: "No follow-ups scheduled after today.",
  all: "No follow-ups yet. They are created when you log a call with a next follow-up.",
};

function Followups() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const tz = edition?.timezone;
  const query = useQuery({
    queryKey: ["followups", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/followups", { params: { query: { edition_id: edition!.id, ...s } } })),
  });
  if (!edition) return <Page><NoEdition /></Page>;

  const columns: Column<Schemas["FollowupOut"]>[] = [
    { key: "lead", header: "Visitor", cell: (f) => <>{f.lead_first_name} <span className="font-normal text-label tabular">{f.lead_registration_code}</span></> },
    { key: "due", header: "Due", cell: (f) => <span className={f.status === "OPEN" && new Date(f.due_at) < new Date() ? "font-medium text-[var(--red-fg)] tabular" : "tabular"}>{formatDateTime(f.due_at, tz)}</span> },
    { key: "status", header: "Status", cell: (f) => <Indicator value={f.status} group="followup_status" /> },
    { key: "note", header: "Note", hideBelow: "lg", cell: (f) => <span className="text-muted">{f.note ?? ""}</span> },
  ];

  return (
    <Page>
      <PageHead title="Follow-ups" meta={`Times in ${tz}.`} />
      <Panel>
        <div className="flex gap-6 overflow-x-auto border-b border-line px-5" role="tablist" aria-label="When">
          {BUCKETS.map((b) => (
            <button
              key={b}
              role="tab"
              aria-selected={s.bucket === b}
              onClick={() => void navigate({ search: (p) => ({ ...p, bucket: b, page: 1 }) })}
              className="-mb-px h-11 border-b-2 border-transparent text-[13px] text-label capitalize hover:text-ink aria-selected:border-ink aria-selected:font-medium aria-selected:text-ink"
            >
              {b}
            </button>
          ))}
        </div>
        <FilterBar>
          <SelectFilter label="Status" allLabel="Open" value={s.status === "OPEN" ? undefined : s.status} onChange={(v) => void navigate({ search: (p) => ({ ...p, status: (v ?? "OPEN") as "OPEN", page: 1 }) })} options={options("followup_status").filter((o) => o.value !== "OPEN")} />
        </FilterBar>
        <ListBody
          query={query}
          onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })}
          onPageSize={(page_size) => void navigate({ search: (p) => ({ ...p, page_size, page: 1 }) })}
          empty={<EmptyState title={EMPTY[s.bucket]} />}
        >
          {(items) => <ListTable caption="Follow-ups" rows={items} columns={columns} rowKey={(f) => f.id} rowLink={(f) => ({ to: "/app/followups/$followupId", params: { followupId: f.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
