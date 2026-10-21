import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useEdition } from "@/lib/edition";
import { ActivityTimeline } from "@/ui/activity";
import { DateFilter, FilterBar, SelectFilter } from "@/ui/filters";
import { Input } from "@/ui/input";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";

const ENTITIES = ["visitor_lead", "visitor_registration", "qr_credential", "user", "role", "exhibition", "exhibition_edition", "gate", "scanner_device", "scan_attempt", "import_job", "export_job", "email_template"];

const search = z.object({
  scope: z.enum(["edition", "all"]).default("edition"),
  entity_type: z.string().optional(),
  action: z.string().optional(),
  from: z.string().optional(),
  to: z.string().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});

export const Route = createFileRoute("/system/audit-log")({ validateSearch: search, component: AuditLog });

function AuditLog() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (p: Partial<z.infer<typeof search>>) => void navigate({ search: (prev) => ({ ...prev, page: 1, ...p }), replace: true });
  const q = useQuery({
    queryKey: ["audit", edition?.id, s],
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(api.GET("/api/v1/audit-logs", {
        params: {
          query: {
            edition_id: s.scope === "edition" ? edition?.id : undefined,
            entity_type: s.entity_type,
            action: s.action,
            occurred_from: s.from ? new Date(`${s.from}T00:00:00`).toISOString() : undefined,
            occurred_to: s.to ? new Date(`${s.to}T23:59:59`).toISOString() : undefined,
            page: s.page,
            page_size: s.page_size,
          },
        },
      })),
  });
  return (
    <Page>
      <PageHead title="Audit Log" meta="Every important change, who made it, and what changed. Secrets are never stored here." />
      <Panel>
        <FilterBar active={Boolean(s.entity_type || s.action || s.from || s.to || s.scope === "all")} onClear={() => void navigate({ search: { scope: "edition", page: 1, page_size: s.page_size } })}>
          <SelectFilter label="Records" allLabel={edition ? `Edition ${edition.code}` : "This edition"} value={s.scope === "all" ? "all" : undefined} onChange={(v) => set({ scope: v === "all" ? "all" : "edition" })} options={[{ value: "all", label: "All, including system" }]} />
          <SelectFilter label="Record type" value={s.entity_type} onChange={(v) => set({ entity_type: v })} options={ENTITIES.map((e) => ({ value: e, label: e.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase()) }))} />
          <div className="flex min-w-[150px] flex-col gap-1 max-sm:flex-1">
            <label htmlFor="audit-action" className="text-[12px] text-label">Action</label>
            <Input id="audit-action" defaultValue={s.action} placeholder="e.g. update" onBlur={(e) => set({ action: e.target.value.trim() || undefined })} />
          </div>
          <DateFilter label="From" value={s.from} onChange={(v) => set({ from: v })} />
          <DateFilter label="To" value={s.to} onChange={(v) => set({ to: v })} />
        </FilterBar>
        <div className="p-5">
          <ListBody query={q} onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })} onPageSize={(page_size) => set({ page_size })} empty={<EmptyState title="No audit entries match." />}>
            {(items) => <ActivityTimeline entries={items} timezone={edition?.timezone} />}
          </ListBody>
        </div>
      </Panel>
    </Page>
  );
}
