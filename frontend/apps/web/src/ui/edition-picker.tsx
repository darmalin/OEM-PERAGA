import { useQueryClient } from "@tanstack/react-query";
import { useId } from "react";

import { useEdition } from "@/lib/edition";

import { Select } from "./input";

/**
 * "Exhibition Type" picker for pages that work in one edition (owner decision 2026-10-22: the
 * edition is chosen on the page, not in the top bar). The choice is remembered for the next page.
 */
export function EditionPicker() {
  const { edition, editions, setEditionId } = useEdition();
  const queryClient = useQueryClient();
  const id = useId();
  if (editions.length === 0) return null;
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-[13px] text-label">Exhibition Type</label>
      <Select
        id={id}
        className="w-auto max-w-[240px]"
        value={edition?.id ?? ""}
        onChange={(e) => {
          setEditionId(e.target.value);
          void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
        }}
      >
        {editions.map((e) => (
          <option key={e.id} value={e.id}>{e.code} · {e.name}</option>
        ))}
      </Select>
    </div>
  );
}
