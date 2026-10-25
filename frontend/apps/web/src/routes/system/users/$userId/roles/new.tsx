import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { useMe } from "@/lib/auth";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/system/users/$userId/roles/new")({ component: AddRole });

const SCOPES = [
  { v: "EDITION", t: "Whole edition", d: "Every record in the edition." },
  { v: "TEAM", t: "Team", d: "Leads owned by members of one team." },
  { v: "OWNED", t: "Own leads", d: "Only leads assigned to this user." },
  { v: "GATE", t: "Gate", d: "One gate's devices and scans." },
] as const;

interface Values {
  role_id: string;
  scope_type: (typeof SCOPES)[number]["v"];
  edition_id: string;
  team_id: string;
  gate_id: string;
}

function AddRole() {
  const { userId } = Route.useParams();
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => call(api.GET("/api/v1/roles")) });
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => call(api.GET("/api/v1/teams")) });
  const form = useForm<Values>({ defaultValues: { role_id: "", scope_type: "EDITION", edition_id: me.editions[0]?.id ?? "", team_id: "", gate_id: "" } });
  const scope = form.watch("scope_type");
  const editionId = form.watch("edition_id");
  const gates = useQuery({
    queryKey: ["gates", editionId],
    enabled: scope === "GATE" && Boolean(editionId),
    queryFn: () => call(api.GET("/api/v1/gates", { params: { query: { edition_id: editionId } } })),
  });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.POST("/api/v1/users/{user_id}/role-assignments", {
        params: { path: { user_id: userId } },
        body: { role_id: v.role_id, scope_type: v.scope_type, edition_id: v.edition_id || null, team_id: v.scope_type === "TEAM" ? v.team_id : null, gate_id: v.scope_type === "GATE" ? v.gate_id : null },
      }));
      void queryClient.invalidateQueries({ queryKey: ["user", userId] });
      notifySuccess("Role added");
      await navigate({ to: "/system/users/$userId", params: { userId } });
    } catch (e) {
      handleFormError(e, form.setError, ["role_id", "edition_id", "team_id", "gate_id"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="Add Role" meta="The role says what the user can do; the scope says on which records." back={{ to: "/system/users/$userId", params: { userId }, label: "User" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Role">
            <Field label="Role" required className="max-w-md" error={form.formState.errors.role_id?.message}>
              {(p) => (
                <Select {...p} {...form.register("role_id", { required: "Choose a role." })}>
                  <option value="">Choose a role</option>
                  {/* Roles above the user's own access are refused by the server; not offered. */}
                  {(roles.data ?? []).filter((r) => r.permissions.every((p) => me.permissions.includes(p))).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </Select>
              )}
            </Field>
          </Section>
          <Section title="Scope">
            <div className="mb-5 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4" role="radiogroup" aria-label="Scope">
              {SCOPES.map((s) => (
                <label key={s.v} className="flex cursor-pointer flex-col gap-0.5 rounded-[10px] border border-line px-4 py-3 has-[:checked]:border-ink has-[:checked]:bg-subtle has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus">
                  <input type="radio" value={s.v} className="sr-only" {...form.register("scope_type")} />
                  <span className="text-[14px] font-medium">{s.t}</span>
                  <span className="text-[12px] text-label">{s.d}</span>
                </label>
              ))}
            </div>
            <FieldGrid>
              <Field label="Edition" required={scope === "GATE"} help={scope !== "GATE" ? "All editions needs global user management rights." : undefined} error={form.formState.errors.edition_id?.message}>
                {(p) => (
                  <Select {...p} {...form.register("edition_id")}>
                    {scope !== "GATE" ? <option value="">All editions</option> : null}
                    {me.editions.map((e) => <option key={e.id} value={e.id}>{e.code} · {e.name}</option>)}
                  </Select>
                )}
              </Field>
              {scope === "TEAM" ? (
                <Field label="Team" required error={form.formState.errors.team_id?.message}>
                  {(p) => (
                    <Select {...p} {...form.register("team_id", { required: "Choose a team." })}>
                      <option value="">Choose a team</option>
                      {(teams.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </Select>
                  )}
                </Field>
              ) : null}
              {scope === "GATE" ? (
                <Field label="Gate" required error={form.formState.errors.gate_id?.message}>
                  {(p) => (
                    <Select {...p} {...form.register("gate_id", { required: "Choose a gate." })}>
                      <option value="">Choose a gate</option>
                      {(gates.data ?? []).map((g) => <option key={g.id} value={g.id}>{g.code} · {g.name}</option>)}
                    </Select>
                  )}
                </Field>
              ) : null}
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/system/users/$userId" params={{ userId }}>Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Add Role</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
