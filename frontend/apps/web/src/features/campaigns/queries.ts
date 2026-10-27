import { api, call, type Schemas } from "@ems/api";
import { queryOptions } from "@tanstack/react-query";

export type CampaignLink = Schemas["CampaignLinkOut"];

/** Campaign links of one edition, or of every edition the user can read (filters). */
export const campaignLinksQuery = (editionId: string | undefined) =>
  queryOptions({
    queryKey: ["campaign-links", editionId ?? "all"],
    queryFn: () => call(api.GET("/api/v1/campaign-links", { params: { query: { edition_id: editionId } } })),
    staleTime: 30_000,
  });
