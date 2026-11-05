import { api, ApiError, call, downloadFile, upload } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Download, FileUp, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { can, useMe } from "@/lib/auth";
import { handleFormError } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Input, Textarea } from "@/ui/input";
import { Facts, FormActions } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

import { type Contract, contractQuery, type ExhibitorLead } from "./queries";

interface ContractValues {
  pic_name: string;
  company_address: string;
  tax_id: string;
  discount_amount: string;
}

const FIELDS = ["pic_name", "company_address", "tax_id", "discount_amount"] as const;

const toValues = (c: Contract): ContractValues => ({
  pic_name: c.pic_name ?? "",
  company_address: c.company_address ?? "",
  tax_id: c.tax_id ?? "",
  discount_amount: c.discount_amount,
});

/** The contract made at Convert: filled in the portal (or here), signed PDF, then read-only. */
export function ContractTab({ lead, timezone }: { lead: ExhibitorLead; timezone?: string }) {
  const q = useQuery({ ...contractQuery(lead.id), enabled: lead.stage === "EXHIBITOR" });
  if (lead.stage !== "EXHIBITOR") {
    return <EmptyState title="The contract is created when the lead is converted to an exhibitor." />;
  }
  if (q.isPending) return <FormSkeleton />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return <ContractBody key={q.data.version} contract={q.data} timezone={timezone} />;
}

function ContractBody({ contract: c, timezone }: { contract: Contract; timezone?: string }) {
  const me = useMe();
  const signed = c.status === "SIGNED";
  return (
    <>
      <Section title="Contract" aside={<Indicator value={c.status} group="contract_status" />}>
        <Facts
          items={[
            ["Number", <span key="n" className="tabular">{c.contract_number}</span>],
            ["Booth", c.booth_code ?? null],
            ["Booth Price", formatMoney(c.booth_price, c.currency)],
            ["Discount", formatMoney(c.discount_amount, c.currency)],
            ["Total", <span key="t" className="font-medium">{formatMoney(c.total_amount, c.currency)}</span>],
            ...(signed ? ([["Signed", formatDateTime(c.signed_at, timezone)]] as [string, string][]) : []),
          ]}
        />
      </Section>
      {signed ? <SignedCopy contract={c} /> : can(me, "exhibitor_lead.update") ? (
        <>
          <ContractForm contract={c} />
          <SignedUpload contract={c} />
        </>
      ) : (
        <Section title="Contract Details">
          <Facts items={[["PIC", c.pic_name], ["Address", c.company_address], ["Tax ID", c.tax_id]]} />
        </Section>
      )}
    </>
  );
}

function ContractForm({ contract: c }: { contract: Contract }) {
  const queryClient = useQueryClient();
  const form = useForm<ContractValues>({ defaultValues: toValues(c) });
  const { errors, isDirty, isSubmitting } = form.formState;
  const save = form.handleSubmit(async (v) => {
    try {
      const updated = await call(
        api.PATCH("/api/v1/exhibitor-leads/{lead_id}/contract", {
          params: { path: { lead_id: c.exhibitor_lead_id } },
          body: { pic_name: v.pic_name, company_address: v.company_address, tax_id: v.tax_id, discount_amount: v.discount_amount || "0", version: c.version },
        }),
      );
      queryClient.setQueryData(contractQuery(c.exhibitor_lead_id).queryKey, updated);
      notifySuccess("Contract saved", updated.contract_number ?? undefined);
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") void queryClient.invalidateQueries({ queryKey: contractQuery(c.exhibitor_lead_id).queryKey });
      handleFormError(e, form.setError, FIELDS);
    }
  });
  return (
    <form onSubmit={save} noValidate>
      <Section title="Contract Details">
        <FieldGrid>
          <Field label="PIC Name" help="Who signs for the exhibitor. Required before signing." error={errors.pic_name?.message}>
            {(p) => <Input {...p} {...form.register("pic_name")} />}
          </Field>
          <Field label="Tax ID (NPWP)" error={errors.tax_id?.message}>
            {(p) => <Input {...p} {...form.register("tax_id")} />}
          </Field>
          <Field label="Discount" help={`In ${c.currency}. The total is the booth price minus the discount.`} error={errors.discount_amount?.message}>
            {(p) => <Input {...p} inputMode="decimal" {...form.register("discount_amount", { pattern: { value: /^\d+(\.\d{1,2})?$/, message: "Enter an amount, e.g. 2500000." } })} />}
          </Field>
          <Field label="Company Address" className="md:col-span-2 lg:col-span-3" help="Required before signing." error={errors.company_address?.message}>
            {(p) => <Textarea {...p} {...form.register("company_address")} />}
          </Field>
        </FieldGrid>
      </Section>
      <FormActions>
        <Button type="button" variant="ghost" disabled={!isDirty} onClick={() => form.reset(toValues(c))}>Discard Changes</Button>
        <Button type="submit" variant="primary" disabled={!isDirty} loading={isSubmitting}>Save Contract</Button>
      </FormActions>
    </form>
  );
}

/** For an exhibitor who sent the signed copy by chat or email instead of the portal. */
function SignedUpload({ contract: c }: { contract: Contract }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("version", String(c.version));
    setBusy(true);
    try {
      const updated = await upload<Contract>(`/api/v1/exhibitor-leads/${c.exhibitor_lead_id}/contract/signed-copy`, form);
      queryClient.setQueryData(contractQuery(c.exhibitor_lead_id).queryKey, updated);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", c.exhibitor_lead_id, "payments"] });
      notifySuccess("Contract signed", updated.contract_number ?? undefined);
    } catch (e) {
      if (e instanceof ApiError) setError(Object.values(e.fields)[0] ?? null);
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Section title="Signed Copy">
      <p className="mb-3 max-w-2xl text-[13px] text-muted">
        Upload the PDF the exhibitor signed. The contract becomes Signed and can no longer change. Save PIC Name and Company Address first.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Signed PDF" error={error ?? undefined} help="PDF, up to 10 MB.">
          {(p) => <Input {...p} type="file" accept="application/pdf,.pdf" className="py-1" onChange={(e) => { setError(null); setFile(e.target.files?.[0] ?? null); }} />}
        </Field>
        <Button type="button" variant="primary" disabled={!file} loading={busy} onClick={() => void send()}>
          <FileUp aria-hidden />Upload and Sign
        </Button>
      </div>
    </Section>
  );
}

function SignedCopy({ contract: c }: { contract: Contract }) {
  const me = useMe();
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      await downloadFile(`/api/v1/exhibitor-leads/${c.exhibitor_lead_id}/contract/signed-copy`, `${c.contract_number ?? "contract"}-signed.pdf`);
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Section title="Contract Details">
      <Facts items={[["PIC", c.pic_name], ["Address", c.company_address], ["Tax ID", c.tax_id], ["Signed File", c.signed_file_name]]} />
      <div className="mt-4 flex flex-wrap gap-2">
        <Button loading={busy} onClick={() => void download()}>
          <Download aria-hidden />Download Signed PDF
        </Button>
        {can(me, "exhibitor.invite") ? (
          <Button asChild variant="ghost">
            <Link to="/app/exhibitor-leads/$leadId/contract-reopen" params={{ leadId: c.exhibitor_lead_id }}>
              <RotateCcw aria-hidden />Reopen Contract
            </Link>
          </Button>
        ) : null}
      </div>
    </Section>
  );
}
