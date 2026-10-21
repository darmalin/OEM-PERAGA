import { api, ApiError, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { meQuery } from "@/lib/auth";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Input } from "@/ui/input";

export const Route = createFileRoute("/login")({
  validateSearch: z.object({ next: z.string().optional() }),
  component: Login,
});

interface LoginForm {
  email: string;
  password: string;
}

function safeNext(next: string | undefined): string {
  // Only same-app paths, never an absolute URL from the query string.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

function Login() {
  const { next } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<LoginForm>();

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      await call(api.POST("/api/v1/auth/login", { body: values }));
      await queryClient.fetchQuery({ ...meQuery, staleTime: 0 });
      await navigate({ to: safeNext(next) as "/" });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The server could not be reached. Try again.");
    }
  });

  return (
    <div className="grid min-h-dvh place-items-center bg-subtle px-4 py-10">
      <div className="w-full max-w-[400px]">
        <p className="mb-6 text-center text-[20px] font-bold tracking-[-0.02em]">EMS</p>
        <form onSubmit={onSubmit} className="rounded-[12px] border border-line bg-bg p-7 max-sm:p-5" noValidate>
          <h1 className="text-[20px] font-semibold">Sign in</h1>
          <p className="mt-1 text-[13px] text-label">Visitor CRM for exhibition teams.</p>
          <div className="mt-6 flex flex-col gap-4">
            <Field label="Email" required error={formState.errors.email?.message}>
              {(p) => (
                <Input {...p} type="email" autoComplete="username" {...register("email", { required: "Enter your email." })} />
              )}
            </Field>
            <Field label="Password" required error={formState.errors.password?.message}>
              {(p) => (
                <Input {...p} type="password" autoComplete="current-password" {...register("password", { required: "Enter your password." })} />
              )}
            </Field>
            {error ? (
              <p role="alert" className="rounded-[8px] bg-[var(--red-bg)] px-3 py-2 text-[13px] text-[var(--red-fg)]">
                {error}
              </p>
            ) : null}
            <Button type="submit" variant="primary" className="mt-1 h-9 w-full" loading={formState.isSubmitting}>
              Sign In
            </Button>
          </div>
        </form>
        <p className="mt-4 text-center text-[13px]">
          <Link to="/forgot-password" className="text-link hover:underline">
            Forgot your password?
          </Link>
        </p>
      </div>
    </div>
  );
}
