import { type FormEvent, useId, useState } from "react";

import { ApiError } from "@/lib/api";
import { activate } from "@/lib/engine";

import { Button } from "./button";

/** First run: the one-time code a gate supervisor created in Gates > Devices. */
export function Activate() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await activate(code);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Cannot reach the server. Activation needs a connection.",
      );
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-8 px-4 py-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Activate this scanner</h1>
        <p className="text-muted">
          Enter the activation code from a gate supervisor. The code works once and binds this
          device to one gate.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div className="space-y-2">
          <label htmlFor={id} className="block font-medium">
            Activation code
          </label>
          <input
            id={id}
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            placeholder="XXXXX-XXXXX"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            className="min-h-14 w-full rounded-control bg-input px-4 text-2xl tracking-widest uppercase placeholder:text-label"
          />
          {error && (
            <p id={`${id}-error`} role="alert" className="text-red-fg">
              {error}
            </p>
          )}
        </div>
        <Button type="submit" variant="primary" className="w-full" disabled={busy || code.trim().length < 6}>
          {busy ? "Activating..." : "Activate Device"}
        </Button>
      </form>
    </main>
  );
}
