import { api, call, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useEdition } from "@/lib/edition";
import { label, options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { FilterBar, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/field-options/")({
  validateSearch: z.object({ field: z.string().optional() }),
  component: FieldOptions,
});

function FieldOptions() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const q = useQuery({
    queryKey: ["field-options", edition?.id, "all", s.field],
    enabled: Boolean(edition),
    queryFn: () => call(api.GET("/api/v1/edition-field-options", { params: { query: { edition_id: edition!.id, include_inactive: true, field: s.field as never } } })),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const columns: Column<Schemas["FieldOptionOut"]>[] = [
    { key: "label", header: "Label", cell: (o) => o.label },
    { key: "field", header: "Field", cell: (o) => label("option_field", o.field) },
    { key: "value", header: "Stored value", hideBelow: "md", cell: (o) => <span className="text-muted">{o.value}</span> },
    { key: "active", header: "Status", cell: (o) => <Indicator value={o.is_active ? "ACTIVE" : "CLOSED"} text={o.is_active ? "Active" : "Hidden"} /> },
  ];
  return (
    <Page>
      <PageHead title="Field Options" meta={`Choices for Business Type, Branch, Exhibition Type, and Product Categories in ${edition.code}.`} actions={<Button asChild variant="primary"><Link to="/app/field-options/new" search={{ field: s.field }}>Add Option</Link></Button>} />
      <Panel>
        <FilterBar><SelectFilter label="Field" value={s.field} onChange={(v) => void navigate({ search: { field: v } })} options={options("option_field")} /></FilterBar>
        <ArrayBody query={q} empty={<EmptyState title="No options yet. The lead form shows an empty list for these fields until you add some." action={<Button asChild variant="primary"><Link to="/app/field-options/new" search={{ field: s.field }}>Add Option</Link></Button>} />}>
          {(rows) => <ListTable caption="Field options" rows={[...rows].sort((a, b) => a.field.localeCompare(b.field) || a.sort_order - b.sort_order)} columns={columns} rowKey={(o) => o.id} rowLink={(o) => ({ to: "/app/field-options/$optionId", params: { optionId: o.id } })} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
