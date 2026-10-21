import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/cn";

const button = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[8px] text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // The ink primary is the one accent action per screen (DESIGN.md).
        primary: "bg-primary text-on-primary hover:opacity-90",
        secondary: "bg-input text-ink hover:bg-hover",
        ghost: "text-ink hover:bg-hover",
        danger: "bg-[var(--red-bg)] text-[var(--red-fg)] hover:brightness-95",
        link: "text-link underline-offset-2 hover:underline px-0 h-auto",
      },
      size: {
        sm: "h-7 px-2.5",
        md: "h-8 px-3 pointer-coarse:h-11",
        icon: "size-8 pointer-coarse:size-11",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, loading, disabled, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(button({ variant, size }), className)}
        disabled={disabled || loading}
        {...props}
      >
        {/* Slot (asChild) takes exactly one child, so the spinner is only for real buttons. */}
        {asChild ? children : (
          <>
            {loading ? <Loader2 className="animate-spin" aria-hidden /> : null}
            {children}
          </>
        )}
      </Comp>
    );
  },
);
Button.displayName = "Button";
