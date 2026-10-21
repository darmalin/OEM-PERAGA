import { downloadFile, type Schemas, upload } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Download, FileSpreadsheet } from "lucide-react";
import { useState } from "react";

import { useEdition } from "@/lib/edition";
import { formatBytes, formatNumber } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/imports/new")({ component: NewImport });

function NewImport() {
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Schemas["PreviewOut"] | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  if (!edition) return <Page><NoEdition /></Page>;

  const pick = async (f: File | null) => {
    setFile(f);
    setPreview(null);
    if (!f) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.set("edition_id", edition.id);
      form.set("file", f);
      const p = await upload<Schemas["PreviewOut"]>("/api/v1/visitor-leads/imports/preview", form);
      setPreview(p);
      setMapping(p.suggested_mapping);
    } catch (e) {
      notifyError(e);
      setFile(null);
    } finally {
      setBusy(false);
    }
  };

  const required = preview?.targets.filter((t) => t.required) ?? [];
  const missing = required.filter((t) => !Object.values(mapping).includes(t.target));

  const start = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.set("edition_id", edition.id);
      form.set("file", file);
      form.set("import_type", "LEADS_ONLY");
      form.set("column_mapping", JSON.stringify(Object.fromEntries(Object.entries(mapping).filter(([, v]) => v))));
      form.set("save_mapping", "true");
      const job = await upload<Schemas["JobAccepted"]>("/api/v1/visitor-leads/imports", form);
      void queryClient.invalidateQueries({ queryKey: ["imports"] });
      notifySuccess("Import started", "You can leave this page; it runs in the background.");
      await navigate({ to: "/app/imports/$jobId", params: { jobId: job.job_id } });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="max-w-[1000px]">
      <PageHead
        title="Import Excel"
        meta={`Into ${edition.code}. Rows become visitor leads; registering them is a separate step.`}
        back={{ to: "/app/imports", label: "Imports" }}
        actions={
          <Button onClick={() => downloadFile(`/api/v1/visitor-leads/imports/template?edition_id=${edition.id}`, `${edition.code}-import-template.xlsx`).catch(notifyError)}>
            <Download aria-hidden />Download Template
          </Button>
        }
      />
      <Panel>
        <Section title="File">
          <label className="flex cursor-pointer flex-col items-center gap-2 rounded-[10px] border border-dashed border-[var(--ink-label)] bg-subtle px-6 py-10 text-center hover:bg-hover has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus">
            <FileSpreadsheet className="size-6 text-muted" strokeWidth={1.5} aria-hidden />
            <span className="text-[14px] font-medium">{file ? file.name : "Choose an .xlsx file"}</span>
            <span className="text-[12px] text-label">{file ? formatBytes(file.size) : "Up to 20 MB and 100,000 rows. The first row holds the column names."}</span>
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="sr-only"
              onChange={(e) => void pick(e.target.files?.[0] ?? null)}
            />
          </label>
          {busy && !preview ? <p className="mt-3 text-[13px] text-label" role="status">Reading the file</p> : null}
        </Section>
        {preview ? (
          <Section title="Columns">
            <p className="mb-4 text-[13px] text-muted">
              {formatNumber(preview.sample_rows)} data rows found. Match each column in your file to an EMS field, or skip it.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <caption className="sr-only">Column mapping</caption>
                <thead>
                  <tr className="border-b border-line text-left text-[12px] text-label">
                    <th scope="col" className="py-2 pr-4 font-normal">Column in file</th>
                    <th scope="col" className="py-2 font-normal">EMS field</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.headers.map((h) => (
                    <tr key={h} className="border-b border-line last:border-b-0">
                      <td className="py-2 pr-4 font-medium">{h || <span className="text-label">(empty header)</span>}</td>
                      <td className="py-2">
                        <Select aria-label={`EMS field for ${h}`} value={mapping[h] ?? ""} onChange={(e) => setMapping((m) => ({ ...m, [h]: e.target.value }))} className="max-w-sm">
                          <option value="">Skip this column</option>
                          {preview.targets.map((t) => (
                            <option key={t.target} value={t.target}>{t.label}{t.required ? " (required)" : ""}</option>
                          ))}
                        </Select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {missing.length > 0 ? (
              <p role="alert" className="mt-4 text-[13px] text-required">Map a column to {missing.map((m) => m.label).join(", ")} before starting.</p>
            ) : null}
          </Section>
        ) : null}
        <FormActions>
          <Button asChild variant="ghost"><Link to="/app/imports">Cancel</Link></Button>
          <Button variant="primary" disabled={!preview || missing.length > 0} loading={busy && Boolean(preview)} onClick={() => void start()}>
            Start Import
          </Button>
        </FormActions>
      </Panel>
    </Page>
  );
}
