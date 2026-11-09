import { api, call } from "@ems/api";
import { type FormEvent, useState } from "react";

import { type Me, messageOf } from "../lib";
import { AuthLayout, Button, Field, Input, Notice } from "../ui";

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
    <AuthLayout title="Sign In" intro="Use the email your sales contact registered for your company.">
      <form onSubmit={(e) => void submit(e)} noValidate className="flex flex-col gap-4">
        {error ? <Notice>{error}</Notice> : null}
        <Field label="Email">{(p) => <Input {...p} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Password">{(p) => <Input {...p} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}</Field>
        <Button type="submit" variant="primary" loading={busy} className="mt-1">Sign In</Button>
        <p className="text-[14px] text-muted">No password yet, or forgot it? Ask your sales contact for a link to set one.</p>
      </form>
    </AuthLayout>
  );
}
