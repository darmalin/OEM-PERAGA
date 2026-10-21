import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useRouterState } from "@tanstack/react-router";
import { useState } from "react";

import { gatesQuery } from "@/features/gate/queries";
import { useEdition } from "@/lib/edition";
import { formatDateTime } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Facts, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, FormSkeleton, NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/devices/$deviceId/")({ component: DeviceDetail });

function DeviceDetail() {
  const { deviceId } = Route.useParams();
  const { edition } = useEdition();
  const queryClient = useQueryClient();
  const handed = useRouterState({ select: (s) => s.location.state.activationCode });
  const [code, setCode] = useState<string | undefined>(handed);
  const [busy, setBusy] = useState(false);
  const devices = useQuery({
    queryKey: ["devices", edition?.id, "all"],
    enabled: Boolean(edition),
    queryFn: () => call(api.GET("/api/v1/gate/devices", { params: { query: { edition_id: edition!.id, page_size: 500 } } })),
  });
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  if (!edition) return <Page><NoEdition /></Page>;
  const d = devices.data?.items.find((x) => x.id === deviceId);
  const gate = gates.data?.find((g) => g.id === d?.gate_id);

  const newCode = async () => {
    setBusy(true);
    try {
      const res = await call(api.POST("/api/v1/gate/devices/{device_id}/activation-code", { params: { path: { device_id: deviceId } } }));
      setCode(res.activation_code);
      void queryClient.invalidateQueries({ queryKey: ["devices"] });
      notifySuccess("New activation code created");
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="max-w-[1000px]">
      <PageHead
        back={{ to: "/app/devices", label: "Devices" }}
        title={d?.name ?? "Scanner device"}
        meta={gate ? `Gate ${gate.code} · ${gate.name}` : null}
        indicators={d ? <Indicator value={d.status} group="device_status" /> : null}
        actions={d && d.status !== "REVOKED" ? <Button asChild variant="danger"><Link to="/app/devices/$deviceId/revoke" params={{ deviceId }}>Revoke Device</Link></Button> : null}
      />
      {devices.isPending ? <Panel><FormSkeleton /></Panel> : !d ? <Panel><EmptyState title="This device is not in the selected edition." /></Panel> : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Panel>
            <PanelHeader title="Activation" />
            {d.status === "PENDING" ? (
              code ? (
                <div className="p-6">
                  <p className="text-[13px] text-label">Activation code. It is shown once; type it on the phone in the scanner app.</p>
                  <p className="mt-3 text-[40px] leading-none font-semibold tracking-[0.08em] tabular" aria-label={`Activation code ${code.split("").join(" ")}`}>{code}</p>
                  <p className="mt-3 text-[13px] text-label tabular">Expires {formatDateTime(d.activation_expires_at, edition.timezone)}</p>
                </div>
              ) : (
                <div className="flex flex-col items-start gap-3 p-6">
                  <p className="text-[14px] text-muted">The activation code is only shown right after it is created. Create a new one to activate this device; the old code stops working.</p>
                  <Button variant="primary" loading={busy} onClick={() => void newCode()}>Create New Code</Button>
                </div>
              )
            ) : d.status === "ACTIVE" ? (
              <p className="p-6 text-[14px] text-muted">This device is active. It scans for gate {gate?.code} only.</p>
            ) : (
              <p className="p-6 text-[14px] text-muted">This device is revoked. Its cache and token stop working the next time it connects.{d.revoke_reason ? ` Reason: ${d.revoke_reason}` : ""}</p>
            )}
          </Panel>
          <Panel>
            <PanelHeader title="Details" />
            <div className="p-5">
              <Facts items={[
                ["Activated", d.activated_at ? formatDateTime(d.activated_at, edition.timezone) : null],
                ["Last seen", d.last_seen_at ? formatDateTime(d.last_seen_at, edition.timezone) : null],
                ["Revoked", d.revoked_at ? formatDateTime(d.revoked_at, edition.timezone) : null],
              ]} />
            </div>
          </Panel>
        </div>
      )}
    </Page>
  );
}
