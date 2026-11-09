import { api, call, type Schemas } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { orderFormsQuery } from "@/features/order-forms/queries";
import { useEdition } from "@/lib/edition";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/order-forms/copy")({ component: CopyForms });

function CopyForms() {
  const queryClient = useQueryClient();
  const { edition, editions } = useEdition();
  const sources = editions.filter((e) => e.id !== edition?.id);
  const [from, setFrom] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Schemas["CopyFormsOut"] | null>(null);
  const preview = useQuery({ ...orderFormsQuery(from), enabled: Boolean(from) });
  if (!edition) return <Page><NoEdition /></Page>;
  const copy = async () => {
    setBusy(true);
    try {
      const out = await call(api.POST("/api/v1/order-forms/copy", { body: { from_edition_id: from, to_edition_id: edition.id } }));
      void queryClient.invalidateQueries({ queryKey: ["order-forms"] });
      setResult(out);
      notifySuccess(`${out.forms_copied} ${out.forms_copied === 1 ? "form" : "forms"} copied`, `${out.items_copied} catalog items`);
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  const count = preview.data?.items.length;
  return (
    <Page className="max-w-[800px]">
      <PageHead edition title="Copy Order Forms" back={{ to: "/app/order-forms", label: "Order Forms" }} meta={`Into ${edition.code}.`} />
      <Panel>
        <div className="flex flex-col gap-4 p-1">
          <p className="max-w-2xl text-[14px] text-muted">
            Copies every form and its catalog, prices and pictures included. Forms whose number already exists in {edition.code} are skipped. Copies start
            unpublished and without dates: set the deadlines of this edition, check the prices, then publish.
          </p>
          <Field label="Copy From" required help={from && count !== undefined ? `${count} ${count === 1 ? "form" : "forms"} in that edition.` : undefined}>
            {(p) => (
              <Select {...p} value={from} onChange={(e) => { setFrom(e.target.value); setResult(null); }}>
                <option value="">Choose an edition</option>
                {sources.map((e) => <option key={e.id} value={e.id}>{e.name} ({e.code})</option>)}
              </Select>
            )}
          </Field>
          {result ? (
            <p className="text-[14px]" role="status">
              Copied {result.forms_copied} {result.forms_copied === 1 ? "form" : "forms"} and {result.items_copied} catalog items.
              {result.skipped_codes.length ? ` Skipped ${result.skipped_codes.join(", ")}: already in ${edition.code}.` : ""}
            </p>
          ) : null}
        </div>
        <FormActions>
          <Button asChild variant="ghost"><Link to="/app/order-forms">{result ? "Back to Order Forms" : "Cancel"}</Link></Button>
          <Button variant="primary" disabled={!from || count === 0} loading={busy} onClick={() => void copy()}>Copy Forms</Button>
        </FormActions>
      </Panel>
    </Page>
  );
}
