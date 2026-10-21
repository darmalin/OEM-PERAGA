import type { Schemas } from "@ems/api";
import { createContext, type ReactNode, useContext, useMemo, useState } from "react";

import { useMe } from "./auth";

type Edition = Schemas["EditionBrief"];
const KEY = "ems.edition";

interface EditionState {
  edition: Edition | null;
  editions: Edition[];
  setEditionId: (id: string) => void;
}

const Ctx = createContext<EditionState | null>(null);

function stored(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function EditionProvider({ children }: { children: ReactNode }) {
  const me = useMe();
  const [selected, setSelected] = useState<string | null>(stored);
  const value = useMemo<EditionState>(() => {
    const editions = me.editions;
    // Saved choice if still allowed, else the first ACTIVE edition, else the newest.
    const edition =
      editions.find((e) => e.id === selected) ??
      editions.find((e) => e.status === "ACTIVE") ??
      editions[0] ??
      null;
    return {
      edition,
      editions,
      setEditionId: (id) => {
        setSelected(id);
        try {
          localStorage.setItem(KEY, id);
        } catch {
          /* private mode: the choice lasts for this tab only */
        }
      },
    };
  }, [me.editions, selected]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useEdition(): EditionState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useEdition outside EditionProvider");
  return ctx;
}

/** The active edition; screens that need one render <NoEdition /> when it is null. */
export function useEditionId(): string | null {
  return useEdition().edition?.id ?? null;
}
