import { api, call, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { useEdition } from "@/lib/edition";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/custom-fields/")({ component: CustomFields });

function CustomFields() {
  const { edition } = useEdition();
  const q = useQuery({
    queryKey: ["custom-fields", edition?.id, "all"],
    enabled: Boolean(edition),
    queryFn: () => call(api.GET("/api/v1/visitor-custom-fields", { params: { query: { edition_id: edition!.id, include_inactive: true } } })),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const columns: Column<Schemas["CustomFieldOut"]>[] = [
    { key: "label", header: "Label", cell: (f) => f.label },
    { key: "key", header: "Key", hideBelow: "md", cell: (f) => <span className="text-muted tabular">{f.field_key}</span> },
    { key: "type", header: "Type", cell: (f) => label("field_type", f.field_type) },
    { key: "req", header: "Required", hideBelow: "lg", cell: (f) => (f.required ? "Yes" : "No") },
    { key: "active", header: "Status", cell: (f) => <Indicator value={f.is_active ? "ACTIVE" : "CLOSED"} text={f.is_active ? "Active" : "Hidden"} /> },
  ];
  return (
    <Page>
      <PageHead edition title="Custom Fields" meta={`Extra visitor fields for ${edition.code}. They appear on the lead form, in imports, and in exports.`} actions={<Button asChild variant="primary"><Link to="/app/custom-fields/new">Add Custom Field</Link></Button>} />
      <Panel>
        <ArrayBody query={q} empty={<EmptyState title="No custom fields in this edition." action={<Button asChild variant="primary"><Link to="/app/custom-fields/new">Add Custom Field</Link></Button>} />}>
          {(rows) => <ListTable caption="Custom fields" rows={[...rows].sort((a, b) => a.sort_order - b.sort_order)} columns={columns} rowKey={(f) => f.id} rowLink={(f) => ({ to: "/app/custom-fields/$fieldId", params: { fieldId: f.id } })} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
