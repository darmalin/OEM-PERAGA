import { api, call } from "@ems/api";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Input } from "@/ui/input";

export const Route = createFileRoute("/forgot-password")({ component: ForgotPassword });

function ForgotPassword() {
  const [sent, setSent] = useState(false);
  const { register, handleSubmit, formState } = useForm<{ email: string }>();
  const onSubmit = handleSubmit(async (values) => {
    try {
      await call(api.POST("/api/v1/auth/password-reset/request", { body: values }));
      setSent(true);
    } catch (e) {
      notifyError(e);
    }
  });
  return (
    <div className="grid min-h-dvh place-items-center bg-subtle px-4 py-10">
      <div className="w-full max-w-[400px] rounded-[12px] border border-line bg-bg p-7 max-sm:p-5">
        <h1 className="text-[20px] font-semibold">Reset your password</h1>
        {sent ? (
          <p className="mt-3 text-[14px] text-muted" role="status">
            If an account uses that email, a reset link is on its way. The link expires in 30 minutes.
          </p>
        ) : (
          <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-4" noValidate>
            <Field label="Email" required error={formState.errors.email?.message}>
              {(p) => <Input {...p} type="email" {...register("email", { required: "Enter your email." })} />}
            </Field>
            <Button type="submit" variant="primary" className="h-9" loading={formState.isSubmitting}>
              Send Reset Link
            </Button>
          </form>
        )}
        <p className="mt-5 text-[13px]">
          <Link to="/login" className="text-link hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
