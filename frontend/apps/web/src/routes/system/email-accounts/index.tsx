import { api, call, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { formatDateTime } from "@/lib/format";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/system/email-accounts/")({ component: Accounts });

export const accountsQuery = { queryKey: ["email-accounts"], queryFn: () => call(api.GET("/api/v1/email-accounts")) };

const COLUMNS: Column<Schemas["EmailAccountOut"]>[] = [
  {
    key: "name",
    header: "Name",
    cell: (a) => (
      <span className="flex items-center gap-2">
        {a.name}
        {a.is_default ? <Indicator value="DEFAULT" text="Default" /> : null}
      </span>
    ),
  },
  { key: "from", header: "From", cell: (a) => <span className="text-muted">{a.from_address}</span> },
  { key: "server", header: "Server", hideBelow: "lg", cell: (a) => <span className="text-muted tabular">{a.host}:{a.port} · {label("smtp_security", a.security)}</span> },
  { key: "status", header: "Status", cell: (a) => <Indicator value={a.is_active ? "ACTIVE" : "INACTIVE"} text={a.is_active ? "Active" : "Inactive"} /> },
  {
    key: "test",
    header: "Last Test",
    hideBelow: "md",
    cell: (a) =>
      a.last_test_at ? (
        <span title={a.last_test_detail ?? undefined}>
          <Indicator value={a.last_test_ok ? "SENT" : "FAILED"} text={a.last_test_ok ? "Passed" : "Failed"} />
          <span className="ml-2 text-[12px] text-label tabular">{formatDateTime(a.last_test_at)}</span>
        </span>
      ) : (
        <span className="text-label">Not tested</span>
      ),
  },
];

function Accounts() {
  const q = useQuery(accountsQuery);
  const add = <Button asChild variant="primary"><Link to="/system/email-accounts/new">Add Email Account</Link></Button>;
  return (
    <Page>
      <PageHead
        title="Email Accounts"
        meta="SMTP accounts email is sent through. The default sends system email (password reset); an edition can pick its own for QR emails. With no account here, the server settings are used."
        actions={add}
      />
      <Panel>
        <ArrayBody query={q} empty={<EmptyState title="No email accounts yet. Email still goes out through the server settings." action={add} />}>
          {(rows) => <ListTable caption="Email accounts" rows={rows} columns={COLUMNS} rowKey={(a) => a.id} rowLink={(a) => ({ to: "/system/email-accounts/$accountId", params: { accountId: a.id } })} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
