import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";
import { useLiveQuery } from "dexie-react-hooks";
import { useEffect, useState } from "react";

import { db } from "@/lib/db";
import { useScanner } from "@/lib/store";

const WARN_BEFORE_MS = 3600_000;

/** Offline list missing, expiring within 1 hour, or expired; and the last sync error. */
export function Notices() {
  const { device, link, error } = useScanner();
  const meta = useLiveQuery(() => db.cache_meta.get("meta"), []);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  const notes: { tone: "amber" | "red"; text: string }[] = [];
  if (link === "error" && error) notes.push({ tone: "red", text: `Sync error: ${error}` });
  if (meta === undefined) {
    notes.push({ tone: "amber", text: "No offline list yet. Offline scans cannot be checked until it downloads." });
  } else {
    const expires = Date.parse(meta.expires_at);
    const at = format(new TZDate(expires, device?.edition_timezone ?? "UTC"), "HH:mm");
    if (now >= expires)
      notes.push({ tone: "red", text: `Offline list expired at ${at}. Offline scans cannot be checked until the device is online.` });
    else if (expires - now <= WARN_BEFORE_MS)
      notes.push({ tone: "amber", text: `Offline list expires at ${at}. Connect to refresh it.` });
  }
  if (notes.length === 0) return null;
  return (
    <div className="space-y-px">
      {notes.map((n) => (
        <p
          key={n.text}
          role={n.tone === "red" ? "alert" : "status"}
          className={n.tone === "red" ? "bg-red-bg px-4 py-2 text-base text-red-fg" : "bg-amber-bg px-4 py-2 text-base text-amber-fg"}
        >
          {n.text}
        </p>
      ))}
    </div>
  );
}
