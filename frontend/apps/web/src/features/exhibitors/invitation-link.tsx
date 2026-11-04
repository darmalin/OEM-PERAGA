import type { Schemas } from "@ems/api";
import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { formatDateTime } from "@/lib/format";
import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Input } from "@/ui/input";

/** The one-time link is shown once: only its hash is stored (exhibitors/service.py). */
export function InvitationLink({ invitation, email, timezone }: { invitation: Schemas["InvitationOut"]; email: string; timezone?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(invitation.url);
      setCopied(true);
    } catch (e) {
      notifyError(e, "Could not copy. Select the link and copy it by hand.");
    }
  };
  return (
    <div className="flex flex-col gap-3">
      <p className="max-w-2xl text-[13px] text-muted">
        Send this link to {email} by chat or email. It opens a page to set the portal password, works once, and expires {formatDateTime(invitation.expires_at, timezone)}.
        It is shown only now; make a new one from the lead if it gets lost.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Invitation Link" className="min-w-0 flex-1">
          {(p) => <Input {...p} value={invitation.url} readOnly onFocus={(e) => e.currentTarget.select()} className="tabular" />}
        </Field>
        <Button onClick={() => void copy()}>
          {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
          {copied ? "Copied" : "Copy Link"}
        </Button>
      </div>
    </div>
  );
}
