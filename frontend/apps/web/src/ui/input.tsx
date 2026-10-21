import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

// Filled inputs without borders, as in the reference screenshot (DESIGN.md).
const base =
  "w-full rounded-[8px] bg-input px-3 text-[14px] text-ink placeholder:text-label hover:bg-hover disabled:cursor-not-allowed disabled:text-muted aria-[invalid=true]:ring-1 aria-[invalid=true]:ring-[var(--required)] read-only:hover:bg-input";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(base, "h-8 pointer-coarse:h-11", className)} {...props} />
  ),
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn(base, "min-h-20 py-2 leading-5", className)} {...props} />
  ),
);
Textarea.displayName = "Textarea";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(base, "select-chevron h-8 cursor-pointer appearance-none pr-8 pointer-coarse:h-11", className)}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";
