import { ApiError } from "@ems/api";
import { useState } from "react";

import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Panel, PanelHeader } from "@/ui/page";

/** Danger panel with an inline confirm; a 409 "still in use" answer stays on the panel. */
export function DeletePanel({ title, description, confirmText, onDelete, onStale }: { title: string; description: string; confirmText: string; onDelete: () => Promise<void>; onStale?: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    try {
      await onDelete();
    } catch (error) {
      setConfirm(false);
      if (error instanceof ApiError && error.status === 409 && error.code.endsWith("_IN_USE")) setBlocked(error.message);
      else {
        if (error instanceof ApiError && error.code === "VERSION_CONFLICT") onStale?.();
        notifyError(error);
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel>
      <PanelHeader title={title} />
      <div className="flex flex-col gap-3 p-5">
        <p className="text-[13px] text-muted">{description}</p>
        {blocked ? <p role="alert" className="rounded-[8px] bg-[var(--red-bg)] px-3 py-2 text-[13px] text-[var(--red-fg)]">{blocked}</p> : null}
        {confirm ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px]">{confirmText}</span>
            <Button variant="danger" loading={busy} onClick={() => void run()}>Confirm Delete</Button>
            <Button variant="ghost" disabled={busy} onClick={() => setConfirm(false)}>Cancel</Button>
          </div>
        ) : (
          <div><Button variant="danger" onClick={() => { setBlocked(null); setConfirm(true); }}>{title}</Button></div>
        )}
      </div>
    </Panel>
  );
}
