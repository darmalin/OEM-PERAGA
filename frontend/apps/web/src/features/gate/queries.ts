import { api, call } from "@ems/api";
import { queryOptions } from "@tanstack/react-query";

export const gatesQuery = (editionId: string) =>
  queryOptions({
    queryKey: ["gates", editionId],
    queryFn: () => call(api.GET("/api/v1/gates", { params: { query: { edition_id: editionId } } })),
  });
