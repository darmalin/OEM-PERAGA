import { api, ApiError, call } from "@ems/api";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Input } from "@/ui/input";

export const Route = createFileRoute("/reset-password")({
  validateSearch: z.object({ token: z.string().default("") }),
  component: ResetPassword,
});

function ResetPassword() {
  const { token } = Route.useSearch();
  const navigate = useNavigate();
  const { register, handleSubmit, formState, setError, watch } = useForm<{ password: string; confirm: string }>();
  const onSubmit = handleSubmit(async ({ password }) => {
    try {
      await call(api.POST("/api/v1/auth/password-reset/confirm", { body: { token, new_password: password } }));
      notifySuccess("Password changed", "Sign in with your new password.");
      await navigate({ to: "/login" });
    } catch (e) {
      if (e instanceof ApiError && e.fields.new_password) setError("password", { message: e.fields.new_password });
      notifyError(e);
    }
  });
  return (
    <div className="grid min-h-dvh place-items-center bg-subtle px-4 py-10">
      <div className="w-full max-w-[400px] rounded-[12px] border border-line bg-bg p-7 max-sm:p-5">
        <h1 className="text-[20px] font-semibold">Choose a new password</h1>
        {!token ? (
          <p className="mt-3 text-[14px] text-muted">This link is incomplete. Open the link from the email again.</p>
        ) : (
          <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-4" noValidate>
            <Field label="New password" required help="At least 8 characters." error={formState.errors.password?.message}>
              {(p) => <Input {...p} type="password" autoComplete="new-password" {...register("password", { required: "Enter a password.", minLength: { value: 8, message: "Use at least 8 characters." } })} />}
            </Field>
            <Field label="Repeat new password" required error={formState.errors.confirm?.message}>
              {(p) => <Input {...p} type="password" autoComplete="new-password" {...register("confirm", { validate: (v) => v === watch("password") || "The passwords do not match." })} />}
            </Field>
            <Button type="submit" variant="primary" className="h-9" loading={formState.isSubmitting}>
              Save Password
            </Button>
          </form>
        )}
        <p className="mt-5 text-[13px]">
          <Link to="/login" className="text-link hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
