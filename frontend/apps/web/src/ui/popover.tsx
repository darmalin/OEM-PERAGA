import * as P from "@radix-ui/react-popover";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export const Popover = P.Root;
export const PopoverTrigger = P.Trigger;
export const PopoverClose = P.Close;

export function PopoverContent({ children, align = "start", className, label }: { children: ReactNode; align?: "start" | "end"; className?: string; label: string }) {
  return (
    <P.Portal>
      <P.Content
        align={align}
        sideOffset={6}
        collisionPadding={16}
        aria-label={label}
        className={cn(
          "z-50 max-h-[var(--radix-popover-content-available-height)] overflow-auto rounded-[8px] border border-line bg-bg p-3 text-[13px] shadow-overlay data-[state=open]:animate-[ems-fade_120ms_ease-out]",
          className,
        )}
      >
        {children}
      </P.Content>
    </P.Portal>
  );
}
