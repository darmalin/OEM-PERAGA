import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check, Minus } from "lucide-react";
import { forwardRef } from "react";

import { cn } from "@/lib/cn";

export const Checkbox = forwardRef<
  HTMLButtonElement,
  CheckboxPrimitive.CheckboxProps
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      "peer relative grid size-4 shrink-0 place-items-center rounded-[4px] border border-[var(--ink-label)] bg-bg data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-on-primary data-[state=indeterminate]:bg-primary data-[state=indeterminate]:text-on-primary pointer-coarse:before:absolute pointer-coarse:before:-inset-3",
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator>
      {props.checked === "indeterminate" ? <Minus className="size-3" /> : <Check className="size-3" strokeWidth={3} />}
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = "Checkbox";
