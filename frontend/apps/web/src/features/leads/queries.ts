import { api, call, type Schemas } from "@ems/api";
import { queryOptions } from "@tanstack/react-query";

export type Lead = Schemas["LeadOut"];
export type LeadItem = Schemas["LeadListItem"];
export type FieldOption = Schemas["FieldOptionOut"];
export type CustomField = Schemas["CustomFieldOut"];

export const leadQuery = (leadId: string) =>
  queryOptions({
    queryKey: ["lead", leadId],
    queryFn: () => call(api.GET("/api/v1/visitor-leads/{lead_id}", { params: { path: { lead_id: leadId } } })),
  });

export const fieldOptionsQuery = (editionId: string) =>
  queryOptions({
    queryKey: ["field-options", editionId],
    queryFn: () => call(api.GET("/api/v1/edition-field-options", { params: { query: { edition_id: editionId } } })),
    staleTime: 5 * 60_000,
  });

export const customFieldsQuery = (editionId: string) =>
  queryOptions({
    queryKey: ["custom-fields", editionId],
    queryFn: () => call(api.GET("/api/v1/visitor-custom-fields", { params: { query: { edition_id: editionId } } })),
    staleTime: 5 * 60_000,
  });

/** Global "Source" master data; inactive ones only for Setup and for a lead that already has one. */
export const leadSourcesQuery = (includeInactive = false) =>
  queryOptions({
    queryKey: ["lead-sources", includeInactive],
    queryFn: () => call(api.GET("/api/v1/lead-sources", { params: { query: { include_inactive: includeInactive } } })),
    staleTime: 5 * 60_000,
  });
