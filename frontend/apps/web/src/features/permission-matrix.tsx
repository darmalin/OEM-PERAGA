import type { Schemas } from "@ems/api";

import { Checkbox } from "@/ui/checkbox";

const GROUPS: Record<string, string> = {
  exhibition: "Exhibitions",
  edition: "Editions",
  visitor: "Visitor leads",
  telemarketing: "Telemarketing",
  registration: "Registration",
  gate: "Gate",
  report: "Reports",
  user: "Users",
  role: "Roles",
  audit_log: "Audit log",
};

/** Permissions grouped by area, one checkbox each. */
export function PermissionMatrix({
  permissions,
  selected,
  onChange,
  readOnly,
}: {
  permissions: Schemas["PermissionOut"][];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  readOnly?: boolean;
}) {
  const groups = new Map<string, Schemas["PermissionOut"][]>();
  for (const p of permissions) {
    const key = p.code.split(".")[0] ?? p.code;
    groups.set(key, [...(groups.get(key) ?? []), p]);
  }
  return (
    <div className="grid grid-cols-1 gap-x-8 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
      {[...groups.entries()].map(([key, perms]) => (
        <fieldset key={key}>
          <legend className="mb-2 text-[13px] font-semibold">{GROUPS[key] ?? key}</legend>
          <div className="flex flex-col gap-2">
            {perms.map((p) => (
              <label key={p.code} className="flex items-start gap-2 text-[13px]">
                <Checkbox
                  className="mt-0.5"
                  checked={selected.has(p.code)}
                  disabled={readOnly}
                  onCheckedChange={(c) => {
                    const next = new Set(selected);
                    if (c === true) next.add(p.code);
                    else next.delete(p.code);
                    onChange(next);
                  }}
                />
                <span>
                  {p.description}
                  <span className="block text-[12px] text-label">{p.code}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
