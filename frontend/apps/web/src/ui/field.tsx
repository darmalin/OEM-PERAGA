import * as Collapsible from "@radix-ui/react-collapsible";
import { ChevronDown } from "lucide-react";
import { type ReactNode, useId } from "react";

import { cn } from "@/lib/cn";

interface FieldProps {
  label: string;
  required?: boolean;
  help?: ReactNode;
  error?: string;
  className?: string;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
}

/** Label above, required star, help, and error linked by aria-describedby (R-32). */
export function Field({ label, required, help, error, className, children }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : help ? `${id}-help` : undefined;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[13px] text-label">
        {label}
        {required ? <span className="ml-0.5 text-required" aria-hidden> *</span> : null}
        {required ? <span className="sr-only"> (required)</span> : null}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": describedBy })}
      {error ? (
        <p id={`${id}-error`} className="text-[12px] text-required">
          {error}
        </p>
      ) : help ? (
        <p id={`${id}-help`} className="text-[12px] text-label">
          {help}
        </p>
      ) : null}
    </div>
  );
}

/** 3 / 2 / 1 columns like the reference form. */
export function FieldGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2 lg:grid-cols-3", className)}>
      {children}
    </div>
  );
}

/** Collapsible section with the chevron header: the second identity motif. */
export function Section({
  title,
  children,
  defaultOpen = true,
  aside,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  aside?: ReactNode;
}) {
  return (
    <Collapsible.Root defaultOpen={defaultOpen} className="border-b border-line last:border-b-0">
      <div className="flex items-center justify-between px-5 pt-5 pb-1 max-md:px-4">
        <Collapsible.Trigger className="group inline-flex items-center gap-2 rounded-[6px] text-[16px] font-semibold text-ink">
          {title}
          <ChevronDown
            className="size-4 text-muted transition-transform group-data-[state=closed]:-rotate-90"
            aria-hidden
          />
        </Collapsible.Trigger>
        {aside}
      </div>
      <Collapsible.Content className="px-5 pt-3 pb-6 max-md:px-4">{children}</Collapsible.Content>
    </Collapsible.Root>
  );
}
