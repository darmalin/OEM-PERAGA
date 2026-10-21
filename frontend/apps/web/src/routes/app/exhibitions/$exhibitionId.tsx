import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { can, useMe } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitions/$exhibitionId")({ component: Exhibition });

function Exhibition() {
  const { exhibitionId } = Route.useParams();
  const me = useMe();
  const queryClient = useQueryClient();
  const ex = useQuery({
    queryKey: ["exhibition", exhibitionId],
    queryFn: () => call(api.GET("/api/v1/exhibitions/{exhibition_id}", { params: { path: { exhibition_id: exhibitionId } } })),
  });
  const editions = useQuery({
    queryKey: ["editions", { exhibition_id: exhibitionId }],
    enabled: can(me, "edition.read"),
    queryFn: () => call(api.GET("/api/v1/editions", { params: { query: { exhibition_id: exhibitionId, page_size: 100 } } })),
  });
  const form = useForm<{ name: string; is_active: boolean }>({ values: ex.data ? { name: ex.data.name, is_active: ex.data.is_active } : undefined });
  const manage = can(me, "exhibition.manage");
  const onSubmit = form.handleSubmit(async (v) => {
    if (!ex.data) return;
    try {
      const updated = await call(api.PATCH("/api/v1/exhibitions/{exhibition_id}", { params: { path: { exhibition_id: exhibitionId } }, body: { version: ex.data.version, ...v } }));
      queryClient.setQueryData(["exhibition", exhibitionId], updated);
      void queryClient.invalidateQueries({ queryKey: ["exhibitions"] });
      notifySuccess("Exhibition saved");
    } catch (e) {
      handleFormError(e, form.setError, ["name"]);
    }
  });
  return (
    <Page className="max-w-[1100px]">
      <PageHead
        back={{ to: "/app/exhibitions", label: "Exhibitions" }}
        title={ex.data?.name ?? "Exhibition"}
        meta={ex.data ? <span className="tabular">{ex.data.code}</span> : null}
        actions={can(me, "edition.manage") && ex.data ? <Button asChild variant="primary"><Link to="/app/editions/new" search={{ exhibition_id: exhibitionId }}>Add Edition</Link></Button> : null}
      />
      {ex.isPending ? <Panel><FormSkeleton /></Panel> : ex.isError ? <Panel><ErrorState error={ex.error} /></Panel> : (
        <div className="flex flex-col gap-6">
          <Panel>
            <form onSubmit={onSubmit} noValidate>
              <Section title="Exhibition">
                <FieldGrid className="lg:grid-cols-2">
                  <Field label="Name" required error={form.formState.errors.name?.message}>
                    {(p) => <Input {...p} readOnly={!manage} {...form.register("name", { required: "Enter a name." })} />}
                  </Field>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-[13px] text-label">Status</span>
                    <label className="flex h-8 items-center gap-2 text-[14px]">
                      <Checkbox checked={form.watch("is_active")} disabled={!manage} onCheckedChange={(c) => form.setValue("is_active", c === true, { shouldDirty: true })} />
                      Active
                    </label>
                  </div>
                </FieldGrid>
              </Section>
              {manage ? <FormActions><Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Exhibition</Button></FormActions> : null}
            </form>
          </Panel>
          <Panel>
            <PanelHeader title="Editions" />
            {editions.data && editions.data.items.length > 0 ? (
              <ul className="divide-y divide-line">
                {editions.data.items.map((e) => (
                  <li key={e.id}>
                    <Link to="/app/editions/$editionId" params={{ editionId: e.id }} className="flex items-center justify-between gap-3 px-5 py-3 text-[14px] hover:bg-subtle">
                      <span><span className="font-medium tabular">{e.code}</span> <span className="text-label">{formatDate(e.start_date)} to {formatDate(e.end_date)}</span></span>
                      <Indicator value={e.status} group="edition_status" />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No editions yet." />
            )}
          </Panel>
        </div>
      )}
    </Page>
  );
}
