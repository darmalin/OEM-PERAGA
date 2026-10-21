import type { Schemas } from "@ems/api";

import { formatDateTime } from "@/lib/format";
import { label } from "@/lib/labels";
import { Indicator } from "@/ui/indicator";
import { type Column, ListTable } from "@/ui/table";

export function ScanTable({ rows, gates, timezone, showProvisional }: { rows: Schemas["ScanOut"][]; gates: Schemas["GateOut"][]; timezone: string; showProvisional?: boolean }) {
  const gate = (id: string) => gates.find((g) => g.id === id)?.code ?? "";
  const columns: Column<Schemas["ScanOut"]>[] = [
    { key: "time", header: "Scanned", cell: (s) => <span className="tabular">{formatDateTime(s.scanned_at, timezone)}</span> },
    { key: "visitor", header: "Visitor", cell: (s) => (s.first_name ? <>{s.first_name} <span className="text-label tabular">{s.registration_code}</span></> : <span className="text-label">Unknown</span>) },
    { key: "result", header: "Result", cell: (s) => <Indicator value={s.result} group="scan_result" /> },
    ...(showProvisional ? [{ key: "prov", header: "Device showed", cell: (s: Schemas["ScanOut"]) => <Indicator value={s.provisional_result} group="scan_result" /> }] : []),
    { key: "gate", header: "Gate", hideBelow: "md", cell: (s) => <span className="tabular">{gate(s.gate_id)}</span> },
    { key: "mode", header: "Mode", hideBelow: "lg", cell: (s) => label("scan_mode", s.mode) + (s.reason ? `: ${s.reason}` : "") },
  ];
  return <ListTable caption="Scans" rows={rows} columns={columns} rowKey={(s) => s.id} />;
}
