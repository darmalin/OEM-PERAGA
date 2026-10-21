import { cn } from "@ems/ui/cn";
import { useLiveQuery } from "dexie-react-hooks";
import { History, RefreshCw } from "lucide-react";

import { db } from "@/lib/db";
import { retry } from "@/lib/engine";
import { useScanner } from "@/lib/store";

/** Gate and edition at all times, plus Online / Offline (n pending) / Sync error + Retry. */
export function Header({ onHistory }: { onHistory: () => void }) {
  const { device, link, syncing, error } = useScanner();
  const pending = useLiveQuery(() => db.scan_queue.where("sync_status").equals("pending").count(), [], 0);

  const indicator =
    link === "error"
      ? { tone: "bg-red-bg text-red-fg", dot: "bg-red-fg", text: "Sync error" }
      : link === "offline"
        ? { tone: "bg-amber-bg text-amber-fg", dot: "bg-amber-fg", text: "Offline" }
        : { tone: "bg-green-bg text-green-fg", dot: "bg-green-fg", text: syncing && pending > 0 ? "Syncing" : "Online" };

  return (
    <header className="flex items-center gap-2 border-b border-line bg-bg px-4 py-2">
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold">
          {device ? `${device.gate_name} · ${device.edition_code}` : "Gate scanner"}
        </p>
        <p
          role="status"
          className={cn("mt-1 inline-flex items-center gap-2 rounded-full px-2.5 py-0.5 text-base font-medium", indicator.tone)}
          title={link === "error" ? (error ?? undefined) : undefined}
        >
          <span aria-hidden className={cn("size-2 rounded-full", indicator.dot)} />
          {indicator.text}
          {pending > 0 && ` (${pending} pending)`}
        </p>
      </div>
      {link === "error" && (
        <button
          type="button"
          onClick={() => void retry()}
          className="inline-flex min-h-14 items-center gap-2 rounded-control bg-input px-4 font-medium"
        >
          <RefreshCw aria-hidden className="size-5" />
          Retry
        </button>
      )}
      <button
        type="button"
        onClick={onHistory}
        aria-label="Recent scans"
        className="inline-flex size-14 items-center justify-center rounded-control bg-input"
      >
        <History aria-hidden className="size-6" />
      </button>
    </header>
  );
}
