import { api, call, type paths, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";

export type ReportName = Schemas["ReportType"];
type Reports = {
  LEADS: Schemas["LeadsReport"];
  TELEMARKETING: Schemas["TelemarketingReport"];
  VERIFICATION: Schemas["VerificationReport"];
  REGISTRATION: Schemas["RegistrationReport"];
  ATTENDANCE: Schemas["AttendanceReport"];
  GATES: Schemas["GatesReport"];
  AGENTS: Schemas["AgentsReport"];
  IMPORTS: Schemas["ImportsReport"];
  EMAILS: Schemas["EmailsReport"];
};

export type ReportParams = Omit<
  paths["/api/v1/reports/visitors"]["get"]["parameters"]["query"],
  "edition_id" | "report"
>;

/** Dashboard numbers poll every 30 s (spec 11: near-real-time by polling). */
export function useReport<K extends ReportName>(
  report: K,
  editionId: string | null,
  params: Partial<ReportParams> = {},
  options: { enabled?: boolean; poll?: boolean } = {},
) {
  return useQuery({
    queryKey: ["report", editionId, report, params],
    enabled: Boolean(editionId) && options.enabled !== false,
    refetchInterval: options.poll ? 30_000 : false,
    queryFn: async () =>
      (await call(
        api.GET("/api/v1/reports/visitors", {
          params: { query: { edition_id: editionId!, report, ...params } },
        }),
      )) as Reports[K],
  });
}
