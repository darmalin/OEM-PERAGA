import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, queryOptions } from "@tanstack/react-query";

export type DashboardSearch = {
  from: string;
  to: string;
  edition?: string;
  country?: string;
  user?: string;
  team?: string;
  source?: string;
  status?: string;
  quality?: string;
  buyer?: string;
  attend?: string;
  b2b?: "yes" | "no";
};

type Group = Schemas["DashboardOut"]["group_by"];

export function dashboardQuery(s: DashboardSearch, group: Group, range?: { from: string; to: string }) {
  const from = range?.from ?? s.from;
  const to = range?.to ?? s.to;
  return queryOptions({
    queryKey: ["dashboard", group, from, to, s],
    placeholderData: keepPreviousData,
    // Near real time, like the old Refresh button but automatic (spec 11).
    refetchInterval: 60_000,
    queryFn: () =>
      call(
        api.GET("/api/v1/reports/dashboard", {
          params: {
            query: {
              date_from: from,
              date_to: to,
              group_by: group,
              edition_id: s.edition,
              country: s.country,
              user_id: s.user,
              team_id: s.team,
              lead_source_id: s.source,
              telemarketing_status: s.status as "NEW" | undefined,
              lead_quality: s.quality as "VALID" | undefined,
              buyer_type: s.buyer as "B_SIDE" | undefined,
              attend: s.attend as "ATTEND" | undefined,
              b2b_matching: s.b2b === "yes" ? true : s.b2b === "no" ? false : undefined,
            },
          },
        }),
      ),
  });
}

export const dashboardOptionsQuery = queryOptions({
  queryKey: ["dashboard", "options"],
  staleTime: 5 * 60_000,
  queryFn: () => call(api.GET("/api/v1/reports/dashboard/options")),
});

export function emailReportQuery(s: DashboardSearch) {
  return queryOptions({
    queryKey: ["dashboard", "email", s.from, s.to, s.edition, s.country, s.user, s.team, s.source],
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
    queryFn: () =>
      call(
        api.GET("/api/v1/reports/dashboard/email", {
          params: {
            query: {
              date_from: s.from,
              date_to: s.to,
              edition_id: s.edition,
              country: s.country,
              user_id: s.user,
              team_id: s.team,
              lead_source_id: s.source,
            },
          },
        }),
      ),
  });
}
