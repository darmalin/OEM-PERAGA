import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { relative } from "@/lib/format";
import { Button } from "@/ui/button";
import { FilterBar, SearchFilter, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const search = z.object({ q: z.string().optional(), active: z.enum(["yes", "no"]).optional(), page: z.number().int().min(1).default(1), page_size: z.number().int().default(20) });
export const Route = createFileRoute("/system/users/")({ validateSearch: search, component: Users });

function Users() {
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const q = useQuery({
    queryKey: ["users", s],
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/users", { params: { query: { q: s.q, is_active: s.active === undefined ? undefined : s.active === "yes", page: s.page, page_size: s.page_size } } })),
  });
  const columns: Column<Schemas["UserOut"]>[] = [
    { key: "name", header: "Name", cell: (u) => u.full_name },
    { key: "email", header: "Email", cell: (u) => <span className="text-muted">{u.email}</span> },
    { key: "status", header: "Status", cell: (u) => <Indicator value={u.is_active ? "ACTIVE" : "CLOSED"} text={u.is_active ? "Active" : "Deactivated"} /> },
    { key: "login", header: "Last sign-in", hideBelow: "md", cell: (u) => <span className="text-label">{u.last_login_at ? relative(u.last_login_at) : "Never"}</span> },
  ];
  return (
    <Page>
      <PageHead title="Users" meta="People who sign in to EMS. What they can do comes from their roles and scopes." actions={<Button asChild variant="primary"><Link to="/system/users/new">Add User</Link></Button>} />
      <Panel>
        <FilterBar>
          <SearchFilter value={s.q} onChange={(v) => void navigate({ search: (p) => ({ ...p, q: v, page: 1 }) })} placeholder="Name or email" label="Search users" />
          <SelectFilter label="Status" value={s.active} onChange={(v) => void navigate({ search: (p) => ({ ...p, active: v as "yes", page: 1 }) })} options={[{ value: "yes", label: "Active" }, { value: "no", label: "Deactivated" }]} />
        </FilterBar>
        <ListBody query={q} onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })} onPageSize={(page_size) => void navigate({ search: (p) => ({ ...p, page_size, page: 1 }) })} empty={<EmptyState title="No users match." />}>
          {(items) => <ListTable caption="Users" rows={items} columns={columns} rowKey={(u) => u.id} rowLink={(u) => ({ to: "/system/users/$userId", params: { userId: u.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
