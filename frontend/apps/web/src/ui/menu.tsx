import * as DM from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export const Menu = DM.Root;
export const MenuTrigger = DM.Trigger;

export function MenuContent({ children, align = "end" }: { children: ReactNode; align?: "start" | "end" }) {
  return (
    <DM.Portal>
      <DM.Content
        align={align}
        sideOffset={6}
        className="z-50 min-w-[200px] rounded-[8px] border border-line bg-bg p-1 text-[13px] shadow-overlay data-[state=open]:animate-[ems-fade_120ms_ease-out]"
      >
        {children}
      </DM.Content>
    </DM.Portal>
  );
}

export function MenuItem({ children, onSelect, className }: { children: ReactNode; onSelect?: () => void; className?: string }) {
  return (
    <DM.Item
      onSelect={onSelect}
      className={cn("flex h-8 cursor-pointer items-center gap-2 rounded-[6px] px-2 outline-none select-none data-[highlighted]:bg-hover [&_svg]:size-4 [&_svg]:text-muted", className)}
    >
      {children}
    </DM.Item>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <DM.Label className="px-2 pt-2 pb-1 text-[12px] text-label">{children}</DM.Label>;
}

export const MenuSeparator = () => <DM.Separator className="my-1 h-px bg-line" />;

export const MenuRadioGroup = DM.RadioGroup;

export function MenuRadioItem({ value, children }: { value: string; children: ReactNode }) {
  return (
    <DM.RadioItem
      value={value}
      className="flex h-8 cursor-pointer items-center justify-between gap-2 rounded-[6px] px-2 outline-none select-none data-[highlighted]:bg-hover"
    >
      {children}
      <DM.ItemIndicator className="text-[12px] text-label">Current</DM.ItemIndicator>
    </DM.RadioItem>
  );
}
