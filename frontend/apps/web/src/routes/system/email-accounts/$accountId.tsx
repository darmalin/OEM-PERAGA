import { api, ApiError, call, type Schemas } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Send, Star } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { formatDateTime } from "@/lib/format";
import { handleFormError } from "@/lib/forms";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Facts, FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, FormSkeleton } from "@/ui/states";

import { ACCOUNT_FIELDS, accountBody, AccountFields, type AccountValues } from "./-form";

export const Route = createFileRoute("/system/email-accounts/$accountId")({ component: EditAccount });

type Account = Schemas["EmailAccountOut"];

const values = (a: Account): AccountValues => ({
  name: a.name, from_name: a.from_name ?? "", from_address: a.from_address, reply_to: a.reply_to ?? "",
  host: a.host, port: String(a.port), security: a.security, username: a.username ?? "", password: "",
  is_active: a.is_active,
});

/** Give up waiting for the worker after this long; the result still lands on the account. */
const TEST_WAIT_MS = 45_000;

function EditAccount() {
  const { accountId } = Route.useParams();
  const queryClient = useQueryClient();
  const [testing, setTesting] = useState(false);
  const load = () => call(api.GET("/api/v1/email-accounts/{account_id}", { params: { path: { account_id: accountId } } }));
  const q = useQuery({ queryKey: ["email-accounts", accountId], queryFn: load });
  const a = q.data;
  const form = useForm<AccountValues>({ values: a ? values(a) : undefined });

  const refresh = (updated: Account) => {
    queryClient.setQueryData(["email-accounts", accountId], updated);
    void queryClient.invalidateQueries({ queryKey: ["email-accounts"], exact: true });
  };

  const onSubmit = form.handleSubmit(async (v) => {
    if (!a) return;
    try {
      const body = accountBody(v);
      const updated = await call(
        api.PATCH("/api/v1/email-accounts/{account_id}", {
          params: { path: { account_id: accountId } },
          body: { ...body, password: body.password ?? undefined, version: a.version },
        }),
      );
      refresh(updated);
      form.reset(values(updated));
      notifySuccess("Email account saved");
    } catch (e) {
      handleFormError(e, form.setError, [...ACCOUNT_FIELDS, "is_active"]);
    }
  });

  const makeDefault = async () => {
    try {
      refresh(await call(api.POST("/api/v1/email-accounts/{account_id}/default", { params: { path: { account_id: accountId } } })));
      notifySuccess("Default account changed", "System email now goes through this account.");
    } catch (e) {
      notifyError(e);
    }
  };

  const sendTest = async () => {
    if (!a) return;
    setTesting(true);
    try {
      const r = await call(api.POST("/api/v1/email-accounts/{account_id}/test", { params: { path: { account_id: accountId } } }));
      notifySuccess("Sending a test email", `To ${r.recipient}. The result appears here in a few seconds.`);
      // The worker sends it; watch the account until the result lands on it.
      const started = Date.now();
      while (Date.now() - started < TEST_WAIT_MS) {
        await new Promise((done) => setTimeout(done, 2000));
        const fresh = await load();
        queryClient.setQueryData(["email-accounts", accountId], fresh);
        if (fresh.last_test_at && fresh.last_test_at !== a.last_test_at) {
          if (fresh.last_test_ok) notifySuccess("Test email sent", fresh.last_test_detail ?? undefined);
          else notifyError(new Error(`Test failed: ${fresh.last_test_detail ?? "unknown error"}`));
          return;
        }
      }
      notifyError(new Error("No result yet. The worker may be busy; check Email Log later."));
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) notifyError(new Error("Too many test emails. Try again later."));
      else notifyError(e);
    } finally {
      setTesting(false);
    }
  };

  return (
    <Page>
      <PageHead
        back={{ to: "/system/email-accounts", label: "Email Accounts" }}
        title={a?.name ?? "Email account"}
        indicators={a ? (
          <>
            {a.is_default ? <Indicator value="DEFAULT" text="Default" /> : null}
            <Indicator value={a.is_active ? "ACTIVE" : "INACTIVE"} text={a.is_active ? "Active" : "Inactive"} />
          </>
        ) : null}
        meta={a?.from_address}
        actions={a ? (
          <>
            {!a.is_default && a.is_active ? <Button onClick={() => void makeDefault()}><Star aria-hidden />Set as Default</Button> : null}
            <Button variant="primary" onClick={() => void sendTest()} loading={testing} disabled={form.formState.isDirty}>
              <Send aria-hidden />Send Test Email
            </Button>
          </>
        ) : null}
      />
      {q.isPending ? <Panel><FormSkeleton /></Panel> : !a ? <Panel><EmptyState title="Email account not found." /></Panel> : (
        <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_300px]">
          <Panel className="min-w-0">
            <form onSubmit={onSubmit} noValidate>
              <AccountFields register={form.register} control={form.control} errors={form.formState.errors} editing hasPassword={a.has_password} />
              <FormActions>
                {form.formState.isDirty ? <span className="mr-auto text-[13px] text-label">Save before sending a test email.</span> : null}
                <Button type="button" variant="ghost" disabled={!form.formState.isDirty} onClick={() => form.reset(values(a))}>Discard Changes</Button>
                <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Email Account</Button>
              </FormActions>
            </form>
          </Panel>
          <aside className="flex flex-col gap-6">
            <Panel>
              <PanelHeader title="Last test" />
              <div className="p-5">
                {a.last_test_at ? (
                  <Facts
                    items={[
                      ["Result", <Indicator key="r" value={a.last_test_ok ? "SENT" : "FAILED"} text={a.last_test_ok ? "Passed" : "Failed"} />],
                      ["When", formatDateTime(a.last_test_at)],
                      ["Detail", a.last_test_detail],
                    ]}
                  />
                ) : (
                  <p className="text-[13px] text-label">Not tested yet. Send Test Email delivers a message to {a.from_address}.</p>
                )}
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="Sent through this account" />
              <div className="p-5 text-[13px]">
                <Link to="/system/email-log" search={{ account: a.id, scope: a.is_default ? "system" : "editions" }} className="text-link hover:underline">Open in Email Log</Link>
              </div>
            </Panel>
          </aside>
        </div>
      )}
    </Page>
  );
}
