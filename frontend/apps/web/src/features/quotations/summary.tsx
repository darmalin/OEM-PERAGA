import { formatDate, formatMoney } from "@/lib/format";
import { label } from "@/lib/labels";

import type { QuotationPreview } from "./queries";

const num = (v: string | null | undefined) => (v == null ? "" : String(Number(v)));

/**
 * The calculation as the PDF prints it, line by line, so staff check the numbers before Create
 * and read the same lines afterwards (docs/EXHIBITOR_QUOTATIONS.md "Calculation").
 */
export function QuotationSummary({ q }: { q: QuotationPreview }) {
  const cur = q.currency;
  const m = (v: string) => formatMoney(v, cur);
  const discount = Number(q.discount_percent) > 0;
  const vat = Number(q.vat_rate) > 0;
  const size = `${q.width_m && q.length_m ? `${num(q.width_m)} m x ${num(q.length_m)} m = ` : ""}${num(q.area_sqm)} sqm${q.booth_code ? ` (booth ${q.booth_code})` : ""}`;
  const rows: [string, string, boolean?][] = [
    ["Stand", label("stand_type", q.stand_type)],
    ["Total space booking", size],
    ...(Number(q.complimentary_sqm) > 0 ? ([["Complimentary space", `${num(q.complimentary_sqm)} sqm, charged ${num(q.charged_sqm)} sqm`]] as [string, string][]) : []),
    [q.stand_type === "SHELL" ? "Shell scheme cost" : "Raw space cost", `${m(q.stand_rate)} /sqm`],
    ...(discount && q.stand_type === "SHELL" ? ([["Raw space cost", `${m(q.raw_rate)} /sqm`]] as [string, string][]) : []),
    ...(discount
      ? ([[`${q.discount_label ?? "Discount"} ${num(q.discount_percent)}%`, `(${num(q.charged_sqm)} sqm x ${m(q.raw_rate)}) x ${num(q.discount_percent)}% = ${m(q.discount_amount)}`]] as [string, string][])
      : []),
    ["Cost of participant", discount ? `${m(q.gross_amount)} - ${m(q.discount_amount)} = ${m(q.cost_amount)}` : `${num(q.charged_sqm)} sqm x ${m(q.stand_rate)} = ${m(q.cost_amount)}`],
    ...(vat ? ([["VAT", `[${m(q.cost_amount)} x tax base ${q.vat_base_num}/${q.vat_base_den}] x ${num(q.vat_rate)}% = ${m(q.vat_amount)}`]] as [string, string][]) : []),
    [vat ? "Total after tax" : "Total", m(q.total_amount), true],
  ];
  return (
    <div className="flex flex-col gap-4 text-[13px]">
      <dl className="grid grid-cols-[minmax(0,140px)_minmax(0,1fr)] gap-x-4 gap-y-1.5 max-sm:grid-cols-1">
        {rows.map(([k, v, strong]) => (
          <div key={k} className="contents">
            <dt className="text-label max-sm:mt-1.5">{k}</dt>
            <dd className={strong ? "text-[15px] font-semibold tabular" : "tabular"}>{v}</dd>
          </div>
        ))}
      </dl>
      <table className="w-full text-[13px]">
        <caption className="sr-only">Terms of payment</caption>
        <thead>
          <tr className="border-b border-line text-left text-label">
            <th scope="col" className="py-1.5 pr-3 font-normal">Terms of Payment</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">%</th>
            <th scope="col" className="py-1.5 pr-3 text-right font-normal">{cur}</th>
            <th scope="col" className="py-1.5 font-normal">Date</th>
          </tr>
        </thead>
        <tbody>
          {q.terms.map((t) => (
            <tr key={t.label} className="border-b border-line last:border-0">
              <td className="py-1.5 pr-3">{t.label}</td>
              <td className="py-1.5 pr-3 text-right tabular">{num(t.percent)}%</td>
              <td className="py-1.5 pr-3 text-right tabular">{m(t.amount)}</td>
              <td className="py-1.5 tabular">{t.due_on ? formatDate(t.due_on) : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {q.includes ? <p className="text-label">Include: {q.includes}</p> : null}
      {q.notes ? <p className="whitespace-pre-line text-muted">{q.notes}</p> : null}
    </div>
  );
}
