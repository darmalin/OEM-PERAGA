export interface ReportHeaderGroup {
  label: string;
  tone: string;
  columns: readonly { label: string }[];
}

/** Shared two-level header for all dashboard reports, including sticky identity columns. */
export function ReportTableHead({ identities, groups }: { identities: readonly string[]; groups: readonly ReportHeaderGroup[] }) {
  return (
    <thead className="sticky top-0 z-10">
      <tr>
        {identities.map((label, index) => <th key={label} scope="col" rowSpan={2} className={`dash-date-heading px-4 py-3 text-left ${index === 0 ? "sticky left-0 z-20 min-w-[165px]" : "min-w-[130px]"}`}>{label}</th>)}
        {groups.map(group => <th key={group.label} scope="colgroup" colSpan={group.columns.length} className={`dash-group-${group.tone} px-3 py-3 text-center`}>{group.label}</th>)}
      </tr>
      <tr>{groups.flatMap(group => group.columns.map(column => <th key={`${group.label}:${column.label}`} scope="col" className="dash-column-heading border border-line px-3 py-2 text-center leading-4">{column.label}</th>))}</tr>
    </thead>
  );
}
