import {
  AtSign,
  Inbox,
  BarChart3,
  Building2,
  CalendarClock,
  ClipboardList,
  DoorOpen,
  FileDown,
  FileUp,
  Gauge,
  HeartPulse,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  Mail,
  MapPin,
  PhoneCall,
  ScanLine,
  ScrollText,
  Settings2,
  ShieldCheck,
  Smartphone,
  Signpost,
  Tags,
  Ticket,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";

import { can, type Me } from "@/lib/auth";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  /** Any one of these permissions shows the item (the backend still checks). */
  perms: string[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export interface PanelDef {
  id: "app" | "system";
  label: string;
  home: string;
  groups: NavGroup[];
}

// Icons are relevant to their page and drawn from one set, 16px / 1.5 stroke (DESIGN.md).
export const PANELS: PanelDef[] = [
  {
    id: "app",
    label: "Admin",
    home: "/app",
    groups: [
      {
        label: "",
        items: [
          { label: "Overview", to: "/app", icon: LayoutDashboard, perms: ["report.view", "visitor.read", "gate.view_history"] },
        ],
      },
      {
        label: "Visitors",
        items: [
          { label: "Visitor Leads", to: "/app/visitor-leads", icon: Users, perms: ["visitor.read"] },
          { label: "My Calls", to: "/app/my-calls", icon: PhoneCall, perms: ["telemarketing.call"] },
          { label: "Follow-ups", to: "/app/followups", icon: CalendarClock, perms: ["telemarketing.followup"] },
          { label: "Registrations", to: "/app/registrations", icon: Ticket, perms: ["registration.read"] },
          { label: "Imports", to: "/app/imports", icon: FileUp, perms: ["visitor.import"] },
          { label: "Exports", to: "/app/exports", icon: FileDown, perms: ["visitor.export", "report.export"] },
        ],
      },
      {
        label: "Gate",
        items: [
          { label: "Gates", to: "/app/gates", icon: DoorOpen, perms: ["gate.manage_devices", "gate.view_history"] },
          { label: "Devices", to: "/app/devices", icon: Smartphone, perms: ["gate.manage_devices"] },
          { label: "Scan History", to: "/app/scans", icon: ScanLine, perms: ["gate.view_history"] },
          { label: "Reconciliation", to: "/app/reconciliation", icon: ListChecks, perms: ["gate.view_history"] },
        ],
      },
      {
        label: "Insights",
        items: [
          { label: "Dashboard", to: "/app/dashboard", icon: Gauge, perms: ["report.view"] },
          { label: "Reports", to: "/app/reports", icon: BarChart3, perms: ["report.view"] },
        ],
      },
      {
        label: "Setup",
        items: [
          { label: "Exhibitions", to: "/app/exhibitions", icon: Building2, perms: ["exhibition.read"] },
          { label: "Editions", to: "/app/editions", icon: ClipboardList, perms: ["edition.read"] },
          { label: "Venues", to: "/app/venues", icon: MapPin, perms: ["exhibition.read", "edition.manage"] },
          { label: "Custom Fields", to: "/app/custom-fields", icon: Settings2, perms: ["edition.manage"] },
          { label: "Field Options", to: "/app/field-options", icon: Tags, perms: ["edition.manage"] },
          { label: "Sources", to: "/app/lead-sources", icon: Signpost, perms: ["exhibition.read", "edition.manage"] },
        ],
      },
    ],
  },
  {
    id: "system",
    label: "System",
    home: "/system",
    groups: [
      {
        label: "",
        items: [
          { label: "Health", to: "/system", icon: HeartPulse, perms: ["user.manage", "role.manage", "audit_log.read"] },
        ],
      },
      {
        label: "Access",
        items: [
          { label: "Users", to: "/system/users", icon: UserCog, perms: ["user.manage"] },
          { label: "Roles", to: "/system/roles", icon: ShieldCheck, perms: ["user.manage", "role.manage"] },
          { label: "Teams", to: "/system/teams", icon: KeyRound, perms: ["user.manage"] },
        ],
      },
      {
        label: "Records",
        items: [
          { label: "Audit Log", to: "/system/audit-log", icon: ScrollText, perms: ["audit_log.read"] },
        ],
      },
      {
        label: "Email",
        items: [
          { label: "Email Accounts", to: "/system/email-accounts", icon: AtSign, perms: ["email_account.manage"] },
          { label: "Email Templates", to: "/system/email-templates", icon: Mail, perms: ["edition.manage"] },
          { label: "Email Log", to: "/system/email-log", icon: Inbox, perms: ["email_log.read", "email_account.manage"] },
        ],
      },
    ],
  },
];

export function visiblePanels(me: Me): PanelDef[] {
  return PANELS.map((p) => ({
    ...p,
    groups: p.groups
      .map((g) => ({ ...g, items: g.items.filter((i) => can(me, ...i.perms)) }))
      .filter((g) => g.items.length > 0),
  })).filter((p) => p.groups.length > 0);
}
