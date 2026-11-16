import { ApiError, downloadFile, upload } from "@ems/api";
import { Download, FileUp, Trash2 } from "lucide-react";
import { useState } from "react";

import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Input } from "@/ui/input";

/** Same limit as the server (PROOF_MAX_FILES): one slip per transfer of a payment paid in parts. */
export const PROOF_MAX_FILES = 5;

interface ProofPayment {
  id: string;
  version: number;
  status: string;
  proof_names?: string[];
}

/**
 * Transfer slips and receipts of one payment, booth or order: the list with a download per file,
 * and while the payment is pending, add up to five and remove a wrong one.
 */
export function PaymentProofs({ url, payment, editable, onChanged, onRemove }: {
  /** The payment's proof URL, without the file number. */
  url: string;
  payment: ProofPayment;
  editable: boolean;
  onChanged: () => Promise<unknown>;
  onRemove: (number: number, version: number) => Promise<unknown>;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  // A new key empties the file input after an upload; the browser keeps its own selection otherwise.
  const [inputKey, setInputKey] = useState(0);
  const names = payment.proof_names ?? [];
  const room = PROOF_MAX_FILES - names.length;

  const send = async () => {
    setBusy("upload");
    setError(null);
    let version = payment.version;
    try {
      // One request per file: each upload moves the payment to its next version.
      for (const file of files.slice(0, room)) {
        const form = new FormData();
        form.append("file", file);
        form.append("version", String(version));
        version = (await upload<ProofPayment>(url, form)).version;
      }
      setFiles([]);
      setInputKey((k) => k + 1);
      notifySuccess(files.length > 1 ? "Proof files attached" : "Proof attached");
    } catch (e) {
      if (e instanceof ApiError) setError(Object.values(e.fields)[0] ?? null);
      notifyError(e);
    } finally {
      await onChanged();
      setBusy(null);
    }
  };
  const remove = async (number: number) => {
    setBusy(`remove-${number}`);
    try {
      await onRemove(number, payment.version);
      await onChanged();
      notifySuccess("Proof removed");
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(null);
    }
  };
  const download = async (number: number) => {
    try {
      // The server names the file, with the extension of the uploaded proof.
      await downloadFile(`${url}/${number}`);
    } catch (e) {
      notifyError(e);
    }
  };

  if (names.length === 0 && !editable) return null;
  return (
    <Section title="Proof">
      {names.length ? (
        <ul className="mb-4 flex flex-col gap-1.5">
          {names.map((name, i) => (
            <li key={`${i}-${name}`} className="flex flex-wrap items-center gap-2 text-[13px]">
              <Button variant="link" onClick={() => void download(i + 1)}><Download aria-hidden />{name}</Button>
              {editable ? (
                <Button variant="ghost" size="icon" aria-label={`Remove ${name}`} loading={busy === `remove-${i + 1}`} disabled={busy !== null} onClick={() => void remove(i + 1)}><Trash2 aria-hidden /></Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {editable && room > 0 ? (
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Transfer Slip or Receipt" help={`PDF, JPG or PNG, up to 10 MB each. Up to ${PROOF_MAX_FILES} files per payment; ${room} more can be added.`} error={error ?? undefined}>
            {(p) => (
              <Input {...p} key={inputKey} type="file" multiple accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" className="py-1"
                onChange={(e) => {
                  const picked = [...(e.target.files ?? [])];
                  setError(picked.length > room ? `Only ${room} more file${room === 1 ? "" : "s"} can be added; the first ${room} will be attached.` : null);
                  setFiles(picked);
                }} />
            )}
          </Field>
          <Button disabled={files.length === 0 || busy !== null} loading={busy === "upload"} onClick={() => void send()}><FileUp aria-hidden />Attach</Button>
        </div>
      ) : editable ? <p className="text-[13px] text-muted">{PROOF_MAX_FILES} files attached, the most a payment holds. Remove one to add another.</p> : null}
    </Section>
  );
}
