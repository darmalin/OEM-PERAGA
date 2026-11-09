import { ApiError, downloadFile, type Schemas, upload } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Download, FileUp } from "lucide-react";
import { useState } from "react";

import { orderFormQuery } from "@/features/order-forms/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/order-forms/$formId/import")({ component: ImportCatalog });

type Result = Schemas["ItemImportOut"];

const FIELD_NAMES: Record<string, string> = {
  section: "Section", code: "Code", name: "Name", description: "Description", size: "Size", unit: "Unit",
  price_regular: "Price Regular", price_surcharge: "Price Surcharge", price_onsite: "Price Onsite",
  max_quantity: "Max Quantity", is_active: "Active", sort_order: "Sort Order",
};

function ImportCatalog() {
  const { formId } = Route.useParams();
  const queryClient = useQueryClient();
  const q = useQuery(orderFormQuery(formId));
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const back = { to: "/app/order-forms/$formId", params: { formId }, search: { tab: "catalog" as const } };
  const send = async () => {
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    setBusy(true);
    setResult(null);
    try {
      const out = await upload<Result>(`/api/v1/order-forms/${formId}/items/import`, body);
      setResult(out);
      if (out.errors.length === 0) {
        void queryClient.invalidateQueries({ queryKey: ["order-forms"] });
        notifySuccess("Catalog imported", `${out.created} added, ${out.updated} updated`);
      }
    } catch (e) {
      if (e instanceof ApiError) setError(Object.values(e.fields)[0] ?? null);
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  const template = async () => {
    try {
      await downloadFile("/api/v1/order-forms/item-import-template");
    } catch (e) {
      notifyError(e);
    }
  };
  const f = q.data;
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="Import Catalog" back={{ ...back, label: f ? `Form ${f.code}` : "Order form" }} meta={f ? `Into ${f.code} · ${f.title}.` : undefined} />
      <Panel>
        {q.isPending ? <FormSkeleton /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : (
          <>
            <Section title="Excel File">
              <div className="flex max-w-3xl flex-col gap-3 text-[14px] text-muted">
                <p>
                  One row per item. Code, Name, and Price Regular are required. A row whose code already exists updates that item; a new code adds one.
                  Items missing from the sheet stay as they are. A blank price cell clears that price; blank Active or Sort Order keep their value.
                </p>
                <p>If any row has an error, nothing is saved: fix the rows listed below and upload again. Up to 1,000 rows and 2 MB.</p>
              </div>
              <div className="mt-4 flex flex-wrap items-end gap-3">
                <Field label="Catalog (.xlsx)" error={error ?? undefined}>
                  {(p) => <Input {...p} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="py-1" onChange={(e) => { setError(null); setResult(null); setFile(e.target.files?.[0] ?? null); }} />}
                </Field>
                <Button type="button" variant="primary" disabled={!file} loading={busy} onClick={() => void send()}><FileUp aria-hidden />Import</Button>
                <Button type="button" variant="ghost" onClick={() => void template()}><Download aria-hidden />Download Template</Button>
              </div>
            </Section>
            {result ? <ImportResult result={result} /> : null}
            <FormActions>
              <Button asChild variant="ghost"><Link {...back}>{result && result.errors.length === 0 ? "Back to Catalog" : "Cancel"}</Link></Button>
            </FormActions>
          </>
        )}
      </Panel>
    </Page>
  );
}

function ImportResult({ result }: { result: Result }) {
  if (result.errors.length === 0) {
    return (
      <Section title="Result">
        <p className="text-[14px]" role="status">{result.created} items added and {result.updated} updated.</p>
      </Section>
    );
  }
  return (
    <Section title={`${result.errors.length} ${result.errors.length === 1 ? "Row Needs" : "Rows Need"} Fixing`}>
      <p className="mb-3 text-[14px] text-muted" role="status">Nothing was saved.</p>
      <table className="w-full max-w-3xl text-[14px]">
        <caption className="sr-only">Rows with errors</caption>
        <thead>
          <tr className="border-b border-line text-left text-[13px] text-label">
            <th scope="col" className="py-2 pr-4 font-normal">Row</th>
            <th scope="col" className="py-2 font-normal">Problem</th>
          </tr>
        </thead>
        <tbody>
          {result.errors.map((e) => (
            <tr key={e.row} className="border-b border-line align-top">
              <td className="py-2 pr-4 tabular">{e.row}</td>
              <td className="py-2">
                {Object.entries(e.errors).map(([field, message]) => (
                  <div key={field}><span className="font-medium">{FIELD_NAMES[field] ?? field}:</span> {message}</div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}
