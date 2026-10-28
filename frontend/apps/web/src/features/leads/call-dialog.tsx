import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/ui/button";

import { CallEditor } from "./call-editor";

/** Native modal keeps keyboard focus inside and makes the board behind it inert. */
export function CallDialog({ leadId, to, onClose }: { leadId: string; to?: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const element = dialog.current!;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    element.showModal();
    return () => { element.close(); document.body.style.overflow = overflow; };
  }, []);
  return (
    <dialog ref={dialog} aria-label="Log Call" aria-modal="true"
      className="fixed inset-0 m-auto max-h-[calc(100dvh-32px)] w-[min(960px,calc(100vw-32px))] max-w-none overflow-y-auto rounded-[12px] border border-line bg-bg p-0 text-ink shadow-overlay backdrop:bg-black/50"
      onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
      <Button className="absolute top-3 right-3" variant="ghost" size="icon" aria-label="Close call form" disabled={busy} onClick={onClose}><X aria-hidden /></Button>
      <CallEditor leadId={leadId} to={to} onComplete={onClose} onCancel={onClose} onBusyChange={setBusy} />
    </dialog>
  );
}
