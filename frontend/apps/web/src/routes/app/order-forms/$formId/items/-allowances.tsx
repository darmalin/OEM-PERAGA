import { api, ApiError, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import type { OrderFormItem } from "@/features/order-forms/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Input } from "@/ui/input";

interface Tier {
  key: string;
  min: string;
  free: string;
}

const tiersOf = (item: OrderFormItem): Tier[] =>
  (item.allowances ?? []).map((t) => ({ key: crypto.randomUUID(), min: String(Number(t.min_area_sqm)), free: String(t.free_quantity) }));

/** Free quantity by booth area (decision O9): saved on its own, like the picture. */
export function AllowancesSection({ formId, item }: { formId: string; item: OrderFormItem }) {
  const queryClient = useQueryClient();
  const [tiers, setTiers] = useState<Tier[]>(() => tiersOf(item));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = tiers.every((t) => /^\d+(\.\d{1,2})?$/.test(t.min) && /^[1-9]\d*$/.test(t.free));
  const dirty = JSON.stringify(tiers.map(({ min, free }) => [Number(min), Number(free)])) !== JSON.stringify((item.allowances ?? []).map((t) => [Number(t.min_area_sqm), t.free_quantity]));
  const set = (key: string, patch: Partial<Tier>) => setTiers((all) => all.map((t) => (t.key === key ? { ...t, ...patch } : t)));
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const saved = await call(
        api.PUT("/api/v1/order-forms/{form_id}/items/{item_id}/allowances", {
          params: { path: { form_id: formId, item_id: item.id } },
          body: { tiers: tiers.map((t) => ({ min_area_sqm: t.min, free_quantity: Number(t.free) })) },
        }),
      );
      await queryClient.invalidateQueries({ queryKey: ["order-forms", "form", formId, "items"] });
      setTiers(tiersOf(saved));
      notifySuccess(saved.allowances?.length ? "Free quantities saved" : "Free quantities removed");
    } catch (e) {
      if (e instanceof ApiError) setError(Object.values(e.fields)[0] ?? null);
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Section title="Free by Booth Size">
      <p className="mb-4 max-w-2xl text-[13px] text-muted">
        How many of this item come free with the booth, e.g. parking passes: from 0 m² 1 free, from 18 m² 2 free. An exhibitor gets the row of the
        largest size their booth reaches, once across all their orders; more than that is charged.
      </p>
      <div className="flex max-w-xl flex-col gap-3">
        {tiers.map((t, n) => (
          <div key={t.key} className="grid grid-cols-[1fr_1fr_auto] items-end gap-3">
            <Field label={`From booth size (m²) ${n + 1}`}>{(p) => <Input {...p} inputMode="decimal" value={t.min} onChange={(e) => set(t.key, { min: e.target.value.trim() })} />}</Field>
            <Field label={`Free quantity ${n + 1}`}>{(p) => <Input {...p} inputMode="numeric" value={t.free} onChange={(e) => set(t.key, { free: e.target.value.trim() })} />}</Field>
            <Button type="button" variant="ghost" aria-label={`Remove row ${n + 1}`} onClick={() => setTiers((all) => all.filter((x) => x.key !== t.key))}><Trash2 aria-hidden /></Button>
          </div>
        ))}
        {error ? <p className="text-[12px] text-required">{error}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="ghost" disabled={tiers.length >= 20} onClick={() => setTiers((all) => [...all, { key: crypto.randomUUID(), min: all.length ? "" : "0", free: "" }])}><Plus aria-hidden />Add Row</Button>
          <Button type="button" disabled={!dirty || !valid} loading={busy} onClick={() => void save()}>Save Free Quantities</Button>
        </div>
      </div>
    </Section>
  );
}
