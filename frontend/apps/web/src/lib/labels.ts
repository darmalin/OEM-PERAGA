/** Display labels for API enum values. Never render the raw codes (FRONTEND_RULES). */
const LABELS: Record<string, Record<string, string>> = {
  telemarketing_status: {
    NEW: "New",
    ANSWER: "Answer",
    NO_ANSWER: "No Answer",
    RECONTACTED: "Recontacted",
    RETRY_NO_ANSWER: "Retry No Answer",
  },
  registration_status: {
    NOT_REGISTERED: "Not Registered",
    REGISTERED: "Registered",
    CANCELLED: "Cancelled",
  },
  qr_status: { NONE: "No QR", ACTIVE: "QR Active", REVOKED: "QR Revoked" },
  attend: {
    ATTEND: "Attend",
    ATTEND_SOURCING: "Attend Sourcing",
    UNDER_CONSIDERATION: "Under Consideration",
    NOT_ATTEND: "Not Attend",
    HANG_UP_IMMEDIATELY: "Hang Up Immediately",
  },
  buyer_type: { B_SIDE: "B-Side", C_SIDE: "C-Side" },
  gender: { MALE: "Male", FEMALE: "Female", OTHER: "Other" },
  source: {
    EXCEL: "Excel",
    API: "API",
    MANUAL: "Manual",
    WEBSITE: "Website",
    TELEMARKETING: "Telemarketing",
  },
  channel: {
    WEBSITE: "Website",
    ADMIN: "Admin",
    TELEMARKETING: "Telemarketing",
    API: "API",
    IMPORT: "Import",
  },
  email_status: {
    QUEUED: "Queued",
    SENDING: "Sending",
    SENT: "Sent",
    FAILED: "Failed",
    CANCELLED: "Cancelled",
  },
  call_result: {
    ANSWER: "Answer",
    NO_ANSWER: "No Answer",
    BUSY: "Busy",
    INVALID_NUMBER: "Invalid Number",
  },
  scan_result: {
    FIRST_ENTRY: "First Entry",
    REPEAT_ENTRY: "Repeat Entry",
    REJECTED_UNKNOWN: "Unknown Code",
    REJECTED_REVOKED: "QR Revoked",
    REJECTED_WRONG_EDITION: "Other Edition",
    REJECTED_CANCELLED: "Registration Cancelled",
  },
  scan_mode: { ONLINE: "Online", OFFLINE: "Offline", OVERRIDE: "Override" },
  device_status: { PENDING: "Pending Activation", ACTIVE: "Active", REVOKED: "Revoked" },
  job_status: {
    QUEUED: "Queued",
    RUNNING: "Running",
    COMPLETED: "Completed",
    COMPLETED_WITH_ERRORS: "Completed With Errors",
    FAILED: "Failed",
    EXPIRED: "Expired",
  },
  edition_status: { DRAFT: "Draft", ACTIVE: "Active", CLOSED: "Closed", ARCHIVED: "Archived" },
  followup_status: { OPEN: "Open", DONE: "Done", CANCELLED: "Cancelled" },
  validity: { VALID: "Valid", INVALID: "Invalid", UNDECIDED: "Undecided" },
  scope_type: { EDITION: "Edition", TEAM: "Team", OWNED: "Own Leads", GATE: "Gate" },
  field_type: {
    text: "Text",
    textarea: "Long Text",
    number: "Number",
    date: "Date",
    select: "Select",
    multi_select: "Multi Select",
    checkbox: "Checkbox",
  },
  option_field: {
    BUSINESS_TYPE: "Business Type",
    BRANCH: "Branch",
    // Retired 2026-10-22: Exhibition Type is now the lead's edition. Kept to label old rows.
    EXHIBITION_TYPE: "Exhibition Type (old)",
    PRODUCT_CATEGORY: "Product Category",
  },
};

export type LabelGroup = keyof typeof LABELS;

export function label(group: LabelGroup, value: string | null | undefined): string {
  if (value == null) return "";
  return LABELS[group]?.[value] ?? value.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

export function options(group: LabelGroup): { value: string; label: string }[] {
  return Object.entries(LABELS[group] ?? {}).map(([value, l]) => ({ value, label: l }));
}
