import { useEffect } from "react";

import { start, stop } from "./lib/engine";
import { useScanner } from "./lib/store";
import { Activate } from "./ui/activate";
import { Gone } from "./ui/gone";
import { ScanScreen } from "./ui/scan-screen";

export function App() {
  const { phase, goneMessage } = useScanner();

  useEffect(() => {
    void start();
    return stop;
  }, []);

  if (phase === "loading") return <p className="sr-only" role="status">Loading</p>;
  if (phase === "activate") return <Activate />;
  if (phase === "gone") return <Gone message={goneMessage} />;
  return <ScanScreen />;
}
