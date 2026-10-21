import { Keyboard } from "lucide-react";
import { type FormEvent, useId, useRef, useState } from "react";

import { Button } from "./button";

/** Fallback when the camera cannot read a QR: type the code printed under it. */
export function ManualEntry({ disabled, onCode }: { disabled: boolean; onCode: (text: string) => void }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const id = useId();

  if (!open)
    return (
      <Button
        className="w-full"
        onClick={() => {
          setOpen(true);
          requestAnimationFrame(() => input.current?.focus());
        }}
      >
        <Keyboard aria-hidden className="size-5" />
        Enter code manually
      </Button>
    );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!code.trim() || disabled) return;
    onCode(code);
    setCode("");
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <label htmlFor={id} className="block font-medium">
        QR code
      </label>
      <div className="flex gap-2">
        <input
          ref={input}
          id={id}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          className="min-h-14 min-w-0 flex-1 rounded-control bg-input px-4"
        />
        <Button type="submit" variant="primary" disabled={disabled || !code.trim()}>
          Check Code
        </Button>
      </div>
      <Button className="w-full" onClick={() => setOpen(false)}>
        Close
      </Button>
    </form>
  );
}
