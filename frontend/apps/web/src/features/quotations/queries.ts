import { api, call, type Schemas } from "@ems/api";
import { queryOptions } from "@tanstack/react-query";

export type Quotation = Schemas["QuotationOut"];
export type QuotationPreview = Schemas["QuotationPreviewOut"];
export type QuotationInput = Schemas["QuotationIn"];
export type QuotationSettings = Schemas["SettingsOut"];

export const quotationSettingsQuery = (editionId: string) =>
  queryOptions({
    queryKey: ["quotation-settings", editionId],
    queryFn: () => call(api.GET("/api/v1/editions/{edition_id}/quotation-settings", { params: { path: { edition_id: editionId } } })),
  });

export const leadQuotationsQuery = (leadId: string) =>
  queryOptions({
    queryKey: ["exhibitor-lead", leadId, "quotations"],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/{lead_id}/quotations", { params: { path: { lead_id: leadId } } })),
  });

export const quotationQuery = (quotationId: string) =>
  queryOptions({
    queryKey: ["quotation", quotationId],
    queryFn: () => call(api.GET("/api/v1/quotations/{quotation_id}", { params: { path: { quotation_id: quotationId } } })),
  });
