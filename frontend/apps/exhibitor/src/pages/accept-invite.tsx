import { api, ApiError, call } from "@ems/api";
import { type FormEvent, useEffect, useState } from "react";

import { type Me, messageOf, navigate } from "../lib";
import { Button, Field, Input, Notice, Panel } from "../ui";

type State = { kind: "checking" } | { kind: "invalid" } | { kind: "error"; message: string } | { kind: "ready"; email: string };

/** The one-time link from the sales team: set a password, then the portal opens signed in. */
export function AcceptInvite({ token, onDone }: { token: string; onDone: (me: Me) => void }) {
  const [state, setState] = useState<State>(token ? { kind: "checking" } : { kind: "invalid" });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{ password?: string; confirm?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    let gone = false;
    call(api.POST("/api/v1/portal/invitations/inspect", { body: { token } }))
      .then((r) => !gone && setState({ kind: "ready", email: r.email }))
      .catch((e: unknown) => {
        if (gone) return;
        setState(e instanceof ApiError && e.status < 500 && e.status !== 429 ? { kind: "invalid" } : { kind: "error", message: messageOf(e) });
      });
    return () => {
      gone = true;
    };
  }, [token]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setErrors({ confirm: "The passwords do not match." });
      return;
    }
    setBusy(true);
    setErrors({});
    try {
      const me = await call(api.POST("/api/v1/portal/invitations/accept", { body: { token, password } }));
      onDone(me);
    } catch (err) {
      if (err instanceof ApiError && err.code === "INVITATION_INVALID") setState({ kind: "invalid" });
      else if (err instanceof ApiError && err.fields.password) setErrors({ password: err.fields.password });
      else setErrors({ form: messageOf(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-[420px]">
      <h1 className="mb-1 text-[24px] leading-8 font-semibold tracking-[-0.01em]">Set Your Password</h1>
      {state.kind === "checking" ? (
        <p role="status" className="py-8 text-label">Checking the link</p>
      ) : state.kind === "invalid" ? (
        <div className="mt-4 flex flex-col gap-4">
          <Notice>This link is invalid, already used, or expired. Ask your sales contact for a new one.</Notice>
          <Button className="self-start" onClick={() => navigate("/login", true)}>Go to Sign In</Button>
        </div>
      ) : state.kind === "error" ? (
        <div className="mt-4"><Notice>{state.message}</Notice></div>
      ) : (
        <>
          <p className="mb-6 text-[14px] text-muted">For <span className="font-medium text-ink">{state.email}</span>. You sign in with this email and password from now on.</p>
          <Panel>
            <form onSubmit={(e) => void submit(e)} noValidate className="flex flex-col gap-4">
              {errors.form ? <Notice>{errors.form}</Notice> : null}
              {/* Lets password managers save the email with the new password. */}
              <input type="email" autoComplete="username" value={state.email} readOnly hidden />
              <Field label="New Password" required help="At least 8 characters, not a common password." error={errors.password}>
                {(p) => <Input {...p} type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
              </Field>
              <Field label="Confirm Password" required error={errors.confirm}>
                {(p) => <Input {...p} type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
              </Field>
              <Button type="submit" variant="primary" loading={busy} disabled={!password}>Set Password and Sign In</Button>
            </form>
          </Panel>
        </>
      )}
    </div>
  );
}
