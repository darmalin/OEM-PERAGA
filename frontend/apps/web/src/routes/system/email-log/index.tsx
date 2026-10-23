import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { formatDateTime } from "@/lib/format";
import { label, options } from "@/lib/labels";
import { DateFilter, FilterBar, SearchFilter, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const search = z.object({
  scope: z.enum(["editions", "system"]).default("editions"),
  edition: z.string().optional(),
  kind: z.string().optional(),
  status: z.string().optional(),
  account: z.string().optional(),
  q: z.string().optional(),
  from: z.string().optional(),
  to: z.string().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});
type Search = z.infer<typeof search>;

export const Route = createFileRoute("/system/email-log/")({ validateSearch: search, component: EmailLog });

type Job = Schemas["EmailJobOut"];

function EmailLog() {
  const me = useMe();
  const { editions } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (p: Partial<Search>) => void navigate({ search: (prev) => ({ ...prev, page: 1, ...p }), replace: true });
  const manage = can(me, "email_account.manage");
  const accounts = useQuery({ queryKey: ["email-accounts"], enabled: manage, queryFn: () => call(api.GET("/api/v1/email-accounts")) });
  const q = useQuery({
    queryKey: ["email-jobs", s],
    placeholderData: keepPreviousData,
    // Keep the list live while emails are still on their way.
    refetchInterval: (query) => (query.state.data?.items.some((j) => j.status === "QUEUED" || j.status === "SENDING") ? 5000 : false),
    queryFn: () =>
      call(api.GET("/api/v1/email-jobs", {
        params: {
          query: {
            scope: s.scope,
            edition_id: s.scope === "editions" ? s.edition : undefined,
            kind: s.kind as "TEST" | undefined,
            status: s.status as "SENT" | undefined,
            account_id: s.account,
            q: s.q,
            queued_from: s.from ? new Date(`${s.from}T00:00:00`).toISOString() : undefined,
            queued_to: s.to ? new Date(`${s.to}T23:59:59`).toISOString() : undefined,
            page: s.page,
            page_size: s.page_size,
          },
        },
      })),
  });
  const editionCode = (id: string | null | undefined) => editions.find((e) => e.id === id)?.code;
  const columns: Column<Job>[] = [
    { key: "queued", header: "Queued", cell: (j) => <span className="text-muted tabular">{formatDateTime(j.queued_at)}</span> },
    { key: "kind", header: "Type", cell: (j) => label("email_kind", j.kind) },
    {
      key: "to",
      header: "To",
      cell: (j) => (
        <span className="flex flex-col leading-tight">
          <span>{j.recipient}</span>
          {j.subject ? <span className="text-[12px] font-normal text-label">{j.subject}</span> : null}
        </span>
      ),
    },
    { key: "edition", header: "Exhibition Type", hideBelow: "xl", cell: (j) => <span className="text-muted">{editionCode(j.edition_id) ?? "System"}</span> },
    { key: "account", header: "Account", hideBelow: "lg", cell: (j) => <span className="text-muted">{j.account_name ?? (j.attempts ? "Server settings" : "")}</span> },
    { key: "status", header: "Status", cell: (j) => <Indicator value={j.status} group="email_status" /> },
    { key: "attempts", header: "Attempts", hideBelow: "md", className: "text-right", cell: (j) => <span className="tabular">{j.attempts}</span> },
    { key: "error", header: "Error", hideBelow: "2xl", cell: (j) => <span className="line-clamp-2 text-[12px] text-red-fg">{j.error_summary ?? ""}</span> },
  ];
  const filtered = Boolean(s.edition || s.kind || s.status || s.account || s.q || s.from || s.to);
  return (
    <Page>
      <PageHead title="Email Log" meta={q.data ? `${q.data.total.toLocaleString("en")} ${q.data.total === 1 ? "email" : "emails"}${filtered ? " matching the filters" : ""}. Every email the system sends, with each attempt.` : "Every email the system sends, with each attempt."} />
      <Panel>
        <FilterBar active={filtered || s.scope === "system"} onClear={() => void navigate({ search: { scope: "editions", page: 1, page_size: s.page_size } })}>
          <SearchFilter value={s.q} onChange={(v) => set({ q: v })} placeholder="Recipient email" label="Search emails" />
          {manage ? (
            <SelectFilter label="Emails" allLabel="Event emails" value={s.scope === "system" ? "system" : undefined} onChange={(v) => set({ scope: v === "system" ? "system" : "editions", edition: undefined })} options={[{ value: "system", label: "System emails" }]} />
          ) : null}
          {s.scope === "editions" ? (
            <SelectFilter label="Exhibition Type" value={s.edition} onChange={(v) => set({ edition: v })} options={editions.map((e) => ({ value: e.id, label: e.code }))} />
          ) : null}
          <SelectFilter label="Type" value={s.kind} onChange={(v) => set({ kind: v })} options={options("email_kind")} />
          <SelectFilter label="Status" value={s.status} onChange={(v) => set({ status: v })} options={options("email_status")} />
          {manage ? (
            <SelectFilter label="Account" value={s.account} onChange={(v) => set({ account: v })} options={(accounts.data ?? []).map((a) => ({ value: a.id, label: a.name }))} />
          ) : null}
          <DateFilter label="From" value={s.from} onChange={(v) => set({ from: v })} />
          <DateFilter label="To" value={s.to} onChange={(v) => set({ to: v })} />
        </FilterBar>
        <ListBody
          query={q}
          onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })}
          onPageSize={(page_size) => set({ page_size })}
          empty={<EmptyState title={filtered ? "No emails match these filters." : "No emails sent yet."} />}
        >
          {(items) => <ListTable caption="Emails" rows={items} columns={columns} rowKey={(j) => j.id} rowLink={(j) => ({ to: "/system/email-log/$jobId", params: { jobId: j.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
