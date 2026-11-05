import { api, call, type Schemas } from "@ems/api";
import { queryOptions } from "@tanstack/react-query";

export type ExhibitorLead = Schemas["ExhibitorLeadOut"];
export type Booth = Schemas["BoothOut"];
export type Contract = Schemas["ContractOut"];
export type Payment = Schemas["PaymentOut"];
export type Payments = Schemas["PaymentsOut"];
export type SalesStage = ExhibitorLead["stage"];

/** Board and filter order; LOST last. */
export const STAGES = ["LEAD", "OPPORTUNITY", "EXHIBITOR", "LOST"] as const;

/** Moves a person can make from each stage (exhibitors/rules.py STAGE_TRANSITIONS). EXHIBITOR is reached by Convert only. */
export const STAGE_MOVES: Record<string, ("LEAD" | "OPPORTUNITY" | "LOST")[]> = {
  LEAD: ["OPPORTUNITY", "LOST"],
  OPPORTUNITY: ["LEAD", "LOST"],
  EXHIBITOR: [],
  LOST: ["LEAD"],
};

export const exhibitorLeadQuery = (leadId: string) =>
  queryOptions({
    queryKey: ["exhibitor-lead", leadId],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/{lead_id}", { params: { path: { lead_id: leadId } } })),
  });

export const contractQuery = (leadId: string) =>
  queryOptions({
    queryKey: ["exhibitor-lead", leadId, "contract"],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/{lead_id}/contract", { params: { path: { lead_id: leadId } } })),
  });

export const paymentsQuery = (leadId: string) =>
  queryOptions({
    queryKey: ["exhibitor-lead", leadId, "payments"],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/{lead_id}/payments", { params: { path: { lead_id: leadId } } })),
  });

export const boothsQuery = (editionId: string, params: { available?: boolean; include_inactive?: boolean } = {}) =>
  queryOptions({
    queryKey: ["booths", editionId, params],
    queryFn: () =>
      call(api.GET("/api/v1/booths", { params: { query: { edition_id: editionId, page_size: 200, ...params } } })),
  });

export const portalAccountQuery = (leadId: string) =>
  queryOptions({
    queryKey: ["exhibitor-lead", leadId, "portal-account"],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/{lead_id}/portal-account", { params: { path: { lead_id: leadId } } })),
  });

/** Users who can own exhibitor leads of the edition, and whether the caller may assign them. */
export const leadOwnersQuery = (editionId: string) =>
  queryOptions({
    queryKey: ["exhibitor-lead-owners", editionId],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/owners", { params: { query: { edition_id: editionId } } })),
    staleTime: 60_000,
  });
