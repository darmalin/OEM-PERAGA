import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useState } from "react";

import { useEdition } from "@/lib/edition";
import { uuid } from "@/lib/forms";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, Section } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, NoEdition, TableSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/visitor-leads/assign")({ component: Assign });

function Assign() {
  const { edition: current, editions } = useEdition();
  const leadIds = useRouterState({ select: (s) => s.location.state.leadIds }) ?? [];
  const editionId = useRouterState({ select: (s) => s.location.state.editionId });
  // The leads' own edition when the caller passed it; the list can show several editions.
  const edition = editions.find((e) => e.id === editionId) ?? current;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"ONE" | "ROUND_ROBIN">("ONE");
  const [agent, setAgent] = useState("");
  const [pool, setPool] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [key] = useState(uuid);
  const agents = useQuery({
    queryKey: ["agents", edition?.id],
    enabled: Boolean(edition),
    queryFn: () => call(api.GET("/api/v1/visitor-leads/assignable-agents", { params: { query: { edition_id: edition!.id } } })),
  });

  if (!edition) return <Page><NoEdition /></Page>;
  const back = leadIds.length === 1
    ? { to: "/app/visitor-leads/$leadId", params: { leadId: leadIds[0]! }, label: "Visitor lead" }
    : { to: "/app/visitor-leads", label: "Visitor Leads" };

  if (leadIds.length === 0) {
    return (
      <Page className="max-w-[960px]">
        <PageHead title="Assign Visitor Leads" back={back} />
        <Panel>
          <EmptyState
            title="No leads were selected. Select leads in the list first, then choose Assign To."
            action={<Button asChild variant="primary"><Link to="/app/visitor-leads">Open Visitor Leads</Link></Button>}
          />
        </Panel>
      </Page>
    );
  }

  const ready = mode === "ONE" ? Boolean(agent) : pool.size > 0;
  const submit = async () => {
    setBusy(true);
    try {
      const method = mode === "ROUND_ROBIN" ? "ROUND_ROBIN" : leadIds.length === 1 ? "MANUAL" : "BULK";
      const res = await call(
        api.POST("/api/v1/visitor-leads/assignments", {
          params: { header: { "Idempotency-Key": key } },
          body: { edition_id: edition.id, method, lead_ids: leadIds, agent_ids: mode === "ONE" ? [agent] : [...pool] },
        }),
      );
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      leadIds.forEach((id) => void queryClient.invalidateQueries({ queryKey: ["lead", id] }));
      if ("job_id" in res) notifySuccess("Assignment queued", "Large batches run in the background; the list updates when it finishes.");
      else notifySuccess(`${res.assigned} assigned`, res.unchanged ? `${res.unchanged} already had that owner.` : undefined);
      await navigate(leadIds.length === 1 ? { to: "/app/visitor-leads/$leadId", params: { leadId: leadIds[0]! } } : { to: "/app/visitor-leads" });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="max-w-[960px]">
      <PageHead
        title={leadIds.length === 1 ? "Assign Visitor Lead" : `Assign ${leadIds.length} Visitor Leads`}
        meta={`Edition ${edition.code}. Every change is kept in the assignment history.`}
        back={back}
      />
      <Panel>
        <Section title="Method">
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Assignment method">
            {[
              { v: "ONE" as const, t: "One agent", d: "All selected leads go to one agent." },
              { v: "ROUND_ROBIN" as const, t: "Round robin", d: "Spread evenly over several agents." },
            ].map((m) => (
              <label key={m.v} className="flex min-w-[240px] flex-1 cursor-pointer flex-col gap-0.5 rounded-[10px] border border-line px-4 py-3 has-[:checked]:border-ink has-[:checked]:bg-subtle has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus">
                <input type="radio" name="mode" value={m.v} checked={mode === m.v} onChange={() => setMode(m.v)} className="sr-only" />
                <span className="text-[14px] font-medium">{m.t}</span>
                <span className="text-[13px] text-label">{m.d}</span>
              </label>
            ))}
          </div>
        </Section>
        <Section title={mode === "ONE" ? "Agent" : "Agents"}>
          {agents.isPending ? (
            <TableSkeleton rows={3} />
          ) : agents.isError ? (
            <ErrorState error={agents.error} />
          ) : agents.data.length === 0 ? (
            <p className="text-[13px] text-muted">No agents can receive leads in this edition yet. Give users the Telemarketing Agent role in System, Users.</p>
          ) : mode === "ONE" ? (
            <Field label="Lead Owner" required className="max-w-md">
              {(p) => (
                <Select {...p} value={agent} onChange={(e) => setAgent(e.target.value)}>
                  <option value="">Choose an agent</option>
                  {agents.data.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                </Select>
              )}
            </Field>
          ) : (
            <div role="group" aria-label="Agents in the rotation" className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {agents.data.map((a) => (
                <label key={a.id} className="flex items-center gap-2 rounded-[8px] bg-input px-3 py-2 text-[14px] pointer-coarse:py-3">
                  <Checkbox
                    checked={pool.has(a.id)}
                    onCheckedChange={(c) =>
                      setPool((prev) => {
                        const next = new Set(prev);
                        if (c === true) next.add(a.id);
                        else next.delete(a.id);
                        return next;
                      })
                    }
                  />
                  <span className="truncate">{a.full_name}</span>
                </label>
              ))}
            </div>
          )}
        </Section>
        <FormActions>
          <Button asChild variant="ghost"><Link to={back.to as "/"} params={back.params as never}>Cancel</Link></Button>
          <Button variant="primary" disabled={!ready} loading={busy} onClick={() => void submit()}>
            {leadIds.length === 1 ? "Assign Lead" : `Assign ${leadIds.length} Leads`}
          </Button>
        </FormActions>
      </Panel>
    </Page>
  );
}
