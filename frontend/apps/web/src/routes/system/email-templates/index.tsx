import { api, call } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useMe } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { Button } from "@/ui/button";
import { FilterBar, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";

export const Route = createFileRoute("/system/email-templates/")({
  validateSearch: z.object({ edition_id: z.string().optional() }),
  component: Templates,
});

function Templates() {
  const me = useMe();
  const { edition_id } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const q = useQuery({
    queryKey: ["email-templates", edition_id ?? "system"],
    queryFn: () => call(api.GET("/api/v1/email-templates", { params: { query: { edition_id, template_key: "QR_CONFIRMATION" } } })),
  });
  return (
    <Page>
      <PageHead
        title="Email Templates"
        meta="QR confirmation email. Each save is a new version; the newest edition version is used, otherwise the system default."
        actions={<Button asChild variant="primary"><Link to="/system/email-templates/new" search={{ edition_id }}>New Version</Link></Button>}
      />
      <Panel>
        <FilterBar>
          <SelectFilter label="Template for" allLabel="System default" value={edition_id} onChange={(v) => void navigate({ search: { edition_id: v } })} options={me.editions.map((e) => ({ value: e.id, label: `${e.code} · ${e.name}` }))} />
        </FilterBar>
        <ArrayBody query={q} empty={<EmptyState title={edition_id ? "This edition uses the system default. Create a version to customise it." : "No system template found."} action={<Button asChild variant="primary"><Link to="/system/email-templates/new" search={{ edition_id }}>New Version</Link></Button>} />}>
          {(rows) => (
            <ul className="divide-y divide-line">
              {rows.map((t, i) => (
                <li key={t.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[14px] font-medium">Version {t.version}: {t.subject}</span>
                    {i === 0 ? <Indicator value="ACTIVE" text="In use" /> : <span className="text-[12px] text-label">Older</span>}
                  </div>
                  <p className="mt-1 text-[12px] text-label tabular">Saved {formatDateTime(t.created_at)}</p>
                  <details className="mt-2 text-[13px]">
                    <summary className="cursor-pointer rounded-[4px] text-link select-none">Show text version</summary>
                    <pre className="mt-2 max-h-60 overflow-auto rounded-[8px] bg-input p-3 text-[12px] whitespace-pre-wrap">{t.body_text}</pre>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
