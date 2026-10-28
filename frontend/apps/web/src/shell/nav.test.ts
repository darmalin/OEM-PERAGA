import { describe, expect, it } from "vitest";

import type { Me } from "@/lib/auth";

import { visiblePanels } from "./nav";

const me = (permissions: string[], global_permissions: string[] = []): Me =>
  ({ user: { id: "u", email: "u@example.test", full_name: "U" }, permissions, global_permissions, grants: [], editions: [], csrf_token: "" }) as Me;

const system = (m: Me) => visiblePanels(m).find((p) => p.id === "system");
const labels = (m: Me) => system(m)?.groups.flatMap((g) => g.items.map((i) => i.label)) ?? [];

describe("System panel by role", () => {
  const editionAdmin = me(["user.manage", "audit_log.read", "email_log.read", "edition.manage", "edition.read"]);

  it("hides platform pages from an edition admin and opens on their first page", () => {
    expect(labels(editionAdmin)).not.toContain("Health");
    expect(labels(editionAdmin)).not.toContain("Email Accounts");
    expect(labels(editionAdmin)).toEqual(expect.arrayContaining(["Users", "Roles", "Teams", "Audit Log", "Email Log"]));
    expect(system(editionAdmin)?.home).toBe("/system/users");
  });

  it("shows everything to a global Super Admin", () => {
    const all = ["user.manage", "role.manage", "audit_log.read", "email_account.manage", "email_log.read", "edition.manage"];
    expect(labels(me(all, all))).toEqual(expect.arrayContaining(["Health", "Email Accounts", "Users", "Roles"]));
    expect(system(me(all, all))?.home).toBe("/system");
  });
});


describe("Visitor Leads workspace", () => {
  it("shows one leads menu without a separate registration menu", () => {
    const items = visiblePanels(me(["visitor.read", "registration.read"])).flatMap((p) => p.groups.flatMap((g) => g.items));
    expect(items.map((item) => item.label)).toContain("Visitor Leads");
    expect(items.map((item) => item.to)).not.toContain("/app/registrations");
  });
});


describe("Call work in Visitor Leads", () => {
  it("does not show a separate My Calls menu", () => {
    const items = visiblePanels(me(["visitor.read", "telemarketing.call"])).flatMap((p) => p.groups.flatMap((g) => g.items));
    expect(items.map((item) => item.to)).toContain("/app/visitor-leads");
    expect(items.map((item) => item.to)).not.toContain("/app/my-calls");
  });
});


describe("Follow-up work in Visitor Leads", () => {
  it("does not show a separate Follow-ups menu", () => {
    const items = visiblePanels(me(["visitor.read", "telemarketing.followup"])).flatMap((p) => p.groups.flatMap((g) => g.items));
    expect(items.map((item) => item.to)).toContain("/app/visitor-leads");
    expect(items.map((item) => item.to)).not.toContain("/app/followups");
  });
});
