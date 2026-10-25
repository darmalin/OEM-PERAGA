import { ListFilter, Plus, X } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/ui/button";
import { Input, Select } from "@/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/ui/popover";

import {
  blankCondition,
  type ChoiceData,
  choicesFor,
  type Condition,
  describe,
  type FieldDef,
  fieldDef,
  FIELDS,
  needsValue,
  type Op,
  opLabel,
  opsFor,
  problem,
  type Value,
} from "./conditions";

/** Frappe-style Filter button: stacked field / operator / value rows, all of which must match. */
export function FilterButton({ value, onChange, data }: { value: Condition[]; onChange: (next: Condition[]) => void; data: ChoiceData }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Condition[]>([]);
  const [checked, setChecked] = useState(false);

  const openChange = (next: boolean) => {
    if (next) {
      setDraft(value.length ? value : [blankCondition()]);
      setChecked(false);
    }
    setOpen(next);
  };
  const update = (i: number, c: Condition) => setDraft((d) => d.map((row, j) => (j === i ? c : row)));
  const apply = () => {
    if (draft.some((c) => problem(c))) {
      setChecked(true);
      return;
    }
    onChange(draft);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={openChange}>
      <PopoverTrigger asChild>
        <Button className="max-sm:flex-1" aria-label={value.length ? `Filter, ${value.length} applied` : "Filter"}>
          <ListFilter aria-hidden />
          Filter
          {value.length ? <span className="rounded-full bg-primary px-1.5 text-[11px] leading-[18px] text-on-primary tabular">{value.length}</span> : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent label="Filters" className="w-[min(680px,calc(100vw-32px))]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            apply();
          }}
          className="flex flex-col gap-3"
        >
          {draft.length === 0 ? <p className="text-label">No filters. Add one to narrow the list.</p> : null}
          <ul className="flex flex-col gap-2">
            {draft.map((c, i) => (
              <ConditionRow
                // Rows are fully controlled, so an index key is safe here.
                key={`${i}-${c.field}`}
                condition={c}
                data={data}
                error={checked ? problem(c) : null}
                onChange={(next) => update(i, next)}
                onRemove={() => setDraft((d) => d.filter((_, j) => j !== i))}
              />
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <Button type="button" variant="ghost" size="sm" onClick={() => setDraft((d) => [...d, blankCondition()])} disabled={draft.length >= 20}>
              <Plus aria-hidden />
              Add a Filter
            </Button>
            <span className="flex-1" />
            {draft.length ? (
              <Button type="button" variant="ghost" size="sm" onClick={() => setDraft([])}>
                Clear All
              </Button>
            ) : null}
            <Button type="submit" variant="primary" size="sm">
              Apply Filters
            </Button>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}

function ConditionRow({ condition: c, data, error, onChange, onRemove }: { condition: Condition; data: ChoiceData; error: string | null; onChange: (c: Condition) => void; onRemove: () => void }) {
  const f = fieldDef(c.field) ?? FIELDS[0]!;
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <li className="flex flex-col gap-1">
      <div className="grid grid-cols-[1fr_1fr_auto] gap-2 sm:grid-cols-[170px_140px_1fr_auto]">
        <label htmlFor={`${id}-field`} className="sr-only">Field</label>
        <Select id={`${id}-field`} value={f.key} onChange={(e) => onChange(blankCondition(e.target.value))}>
          {FIELDS.map((o) => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </Select>
        <label htmlFor={`${id}-op`} className="sr-only">Operator</label>
        <Select
          id={`${id}-op`}
          value={c.op}
          onChange={(e) => {
            const op = e.target.value as Op;
            // Between holds two dates, the others one: start the value over when that changes.
            const keep = (op === "between") === (c.op === "between");
            onChange({ ...c, op, value: needsValue(op) && keep ? c.value : f.kind === "bool" ? true : undefined });
          }}
        >
          {opsFor(f).map((op) => (
            <option key={op} value={op}>{opLabel(op, f.kind)}</option>
          ))}
        </Select>
        <Button type="button" variant="ghost" size="icon" onClick={onRemove} aria-label={`Remove filter: ${describe(c, data)}`} className="sm:order-last">
          <X aria-hidden />
        </Button>
        <div className="col-span-3 sm:col-span-1">
          {needsValue(c.op) ? (
            <ValueInput id={id} field={f} condition={c} data={data} invalid={Boolean(error)} describedBy={error ? errorId : undefined} onChange={(value) => onChange({ ...c, value })} />
          ) : null}
        </div>
      </div>
      {error ? <p id={errorId} className="text-[12px] text-[var(--required)]">{error}</p> : null}
    </li>
  );
}

function ValueInput({
  id,
  field: f,
  condition: c,
  data,
  invalid,
  describedBy,
  onChange,
}: {
  id: string;
  field: FieldDef;
  condition: Condition;
  data: ChoiceData;
  invalid: boolean;
  describedBy?: string;
  onChange: (v: Value | undefined) => void;
}) {
  const common = { id: `${id}-value`, "aria-invalid": invalid, "aria-describedby": describedBy };
  const label = <label htmlFor={`${id}-value`} className="sr-only">Value</label>;
  switch (f.kind) {
    case "choice":
      return (
        <>
          {label}
          <Select {...common} value={typeof c.value === "string" ? c.value : ""} onChange={(e) => onChange(e.target.value || undefined)}>
            <option value="">Choose…</option>
            {choicesFor(f, data).map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
        </>
      );
    case "bool":
      return (
        <>
          {label}
          <Select {...common} value={c.value === false ? "no" : "yes"} onChange={(e) => onChange(e.target.value === "yes")}>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </Select>
        </>
      );
    case "date":
      if (c.op === "between") {
        const [from = "", to = ""] = Array.isArray(c.value) ? c.value : [];
        return (
          <div className="flex items-center gap-2">
            <label htmlFor={`${id}-value`} className="sr-only">From</label>
            <Input {...common} type="date" value={from} onChange={(e) => onChange([e.target.value, to])} />
            <span className="text-label">to</span>
            <label htmlFor={`${id}-to`} className="sr-only">To</label>
            <Input id={`${id}-to`} aria-invalid={invalid} type="date" value={to} onChange={(e) => onChange([from, e.target.value])} />
          </div>
        );
      }
      return (
        <>
          {label}
          <Input {...common} type="date" value={typeof c.value === "string" ? c.value : ""} onChange={(e) => onChange(e.target.value || undefined)} />
        </>
      );
    case "number":
      return (
        <>
          {label}
          <Input {...common} type="number" min={0} step={1} inputMode="numeric" value={typeof c.value === "number" ? c.value : ""} onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} />
        </>
      );
    case "text":
      return (
        <>
          {label}
          <Input {...common} value={typeof c.value === "string" ? c.value : ""} inputMode={f.key === "phone" ? "tel" : "text"} autoComplete="off" onChange={(e) => onChange(e.target.value)} />
        </>
      );
  }
}

/** Applied conditions as removable chips under the filter bar. */
export function ConditionChips({ value, onChange, data }: { value: Condition[]; onChange: (next: Condition[]) => void; data: ChoiceData }) {
  if (!value.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5 border-b border-line px-4 py-2" aria-label="Applied filters">
      {value.map((c, i) => {
        const text = describe(c, data);
        return (
          <li key={`${i}-${c.field}`} className="flex items-center gap-1 rounded-full bg-input py-0.5 pr-1 pl-2.5 text-[12px]">
            <span>{text}</span>
            <button
              type="button"
              onClick={() => onChange(value.filter((_, j) => j !== i))}
              className="grid size-5 place-items-center rounded-full text-label hover:bg-hover hover:text-ink pointer-coarse:size-8"
              aria-label={`Remove filter: ${text}`}
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
