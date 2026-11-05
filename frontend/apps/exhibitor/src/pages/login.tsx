import { api, call } from "@ems/api";
import { type FormEvent, useState } from "react";

import { type Me, messageOf } from "../lib";
import { Button, Field, Input, Notice, Panel } from "../ui";

export function Login({ onDone }: { onDone: (me: Me) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onDone(await call(api.POST("/api/v1/portal/auth/login", { body: { email: email.trim(), password } })));
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-[420px]">
      <h1 className="mb-1 text-[24px] leading-8 font-semibold tracking-[-0.01em]">Sign In</h1>
      <p className="mb-6 text-[14px] text-muted">For exhibitors: fill in your contract and follow your payments.</p>
      <Panel>
        <form onSubmit={(e) => void submit(e)} noValidate className="flex flex-col gap-4">
          {error ? <Notice>{error}</Notice> : null}
          <Field label="Email">{(p) => <Input {...p} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          <Field label="Password">{(p) => <Input {...p} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}</Field>
          <Button type="submit" variant="primary" loading={busy}>Sign In</Button>
          <p className="text-[13px] text-label">No password yet, or forgot it? Ask your sales contact for a link to set one.</p>
        </form>
      </Panel>
    </div>
  );
}
