import { ShieldOff } from "lucide-react";

import { startOver } from "@/lib/engine";

import { Button } from "./button";

/** The server revoked or no longer knows this device; local data is already wiped. */
export function Gone({ message }: { message: string | null }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-8">
      <ShieldOff aria-hidden className="size-12 text-red-fg" strokeWidth={1.5} />
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">This device cannot scan</h1>
        <p role="alert">{message ?? "This device was revoked. Ask a gate supervisor."}</p>
        <p className="text-muted">Its offline list and scan queue were removed from this phone.</p>
      </div>
      <Button variant="primary" onClick={startOver}>
        Enter New Activation Code
      </Button>
    </main>
  );
}
