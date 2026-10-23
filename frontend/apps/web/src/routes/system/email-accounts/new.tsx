import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

import { ACCOUNT_FIELDS, accountBody, AccountFields, type AccountValues, emptyAccount } from "./-form";

export const Route = createFileRoute("/system/email-accounts/new")({ component: NewAccount });

function NewAccount() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<AccountValues>({ defaultValues: emptyAccount() });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const account = await call(api.POST("/api/v1/email-accounts", { body: accountBody(v) }));
      void queryClient.invalidateQueries({ queryKey: ["email-accounts"] });
      notifySuccess("Email account added", account.is_default ? "It is the default account." : "Send a test email to check it.");
      await navigate({ to: "/system/email-accounts/$accountId", params: { accountId: account.id } });
    } catch (e) {
      handleFormError(e, form.setError, ACCOUNT_FIELDS);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="New Email Account" back={{ to: "/system/email-accounts", label: "Email Accounts" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <AccountFields register={form.register} control={form.control} errors={form.formState.errors} editing={false} />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/system/email-accounts">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Email Account</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
