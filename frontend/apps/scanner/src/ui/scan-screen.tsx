import { lazy, Suspense, useCallback, useRef, useState } from "react";

import { type Outcome, scan } from "@/lib/engine";

import { Header } from "./header";
import { History } from "./history";
import { ManualEntry } from "./manual";
import { Notices } from "./notices";
import { Result } from "./result";

// The QR decoder is most of the bundle; the activation screen does not need it.
const Camera = lazy(() => import("./camera").then((m) => ({ default: m.Camera })));

export function ScanScreen() {
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const busy = useRef(false);

  const onCode = useCallback(async (text: string, source: "camera" | "manual") => {
    if (busy.current) return;
    busy.current = true;
    try {
      const out = await scan(text, source);
      if (out) setOutcome(out);
    } finally {
      busy.current = false;
    }
  }, []);
  const onDone = useCallback(() => setOutcome(null), []);

  if (showHistory) return <History onBack={() => setShowHistory(false)} />;

  return (
    <main className="flex h-dvh flex-col bg-bg">
      <Header onHistory={() => setShowHistory(true)} />
      <Notices />
      <Suspense fallback={<div className="flex-1 bg-black" />}>
        <Camera paused={outcome !== null} onCode={(t) => void onCode(t, "camera")} />
      </Suspense>
      <div className="border-t border-line p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <ManualEntry disabled={outcome !== null} onCode={(t) => void onCode(t, "manual")} />
      </div>
      {outcome && <Result outcome={outcome} onDone={onDone} />}
    </main>
  );
}
