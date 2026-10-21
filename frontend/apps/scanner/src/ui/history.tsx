import { cn } from "@ems/ui/cn";
import { useLiveQuery } from "dexie-react-hooks";
import { ArrowLeft } from "lucide-react";

import { db, type QueuedScan } from "@/lib/db";
import { effectiveResult } from "@/lib/decide";
import { RESULT_LABEL } from "@/lib/labels";
import { useScanner } from "@/lib/store";
import { localTime } from "@/lib/time";

const STATUS: Record<QueuedScan["sync_status"], { text: string; tone: string }> = {
  pending: { text: "Pending", tone: "bg-amber-bg text-amber-fg" },
  synced: { text: "Synced", tone: "bg-green-bg text-green-fg" },
  rejected: { text: "Rejected", tone: "bg-red-bg text-red-fg" },
};

/** The last scans on this device, with results the server changed after sync marked. */
export function History({ onBack }: { onBack: () => void }) {
  const { device } = useScanner();
  const scans = useLiveQuery(() => db.scan_queue.orderBy("scanned_at").reverse().limit(50).toArray(), []);
  const tz = device?.edition_timezone ?? "UTC";

  return (
    <main className="flex min-h-dvh flex-col bg-bg">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to scanner"
          className="inline-flex size-14 items-center justify-center rounded-control bg-input"
        >
          <ArrowLeft aria-hidden className="size-6" />
        </button>
        <h1 className="text-xl font-semibold">Recent scans</h1>
      </header>
      {scans === undefined ? null : scans.length === 0 ? (
        <p className="px-4 py-8 text-center text-muted">No scans on this device yet.</p>
      ) : (
        <ul className="divide-y divide-line">
          {scans.map((s) => {
            const r = effectiveResult(s);
            return (
              <li key={s.scan_event_id} className="flex items-center gap-3 px-4 py-3">
                <span className="w-24 shrink-0 tabular-nums text-muted">{localTime(s.scanned_at, tz)}</span>
                <span className="min-w-0 flex-1">
                  {r ? RESULT_LABEL[r] : "Not checked"}
                  {s.provisional_result && s.sync_status === "pending" && (
                    <span className="block text-base text-muted">Provisional</span>
                  )}
                  {s.changed && s.provisional_result && (
                    <span className="block text-base text-red-fg">
                      Changed after sync, device showed {RESULT_LABEL[s.provisional_result]}
                    </span>
                  )}
                </span>
                <span className={cn("shrink-0 rounded-full px-2.5 py-0.5 text-base font-medium", STATUS[s.sync_status].tone)}>
                  {STATUS[s.sync_status].text}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
