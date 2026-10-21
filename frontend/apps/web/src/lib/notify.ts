import { ApiError } from "@ems/api";
import { toast } from "sonner";

export function notifySuccess(message: string, description?: string): void {
  toast.success(message, { description, duration: 4000 });
}

/** Errors stay until dismissed and carry the request ID for support (DESIGN.md "Toasts"). */
export function notifyError(error: unknown, fallback = "Something went wrong."): void {
  if (error instanceof ApiError) {
    toast.error(error.message, {
      description: error.requestId ? `Request ID ${error.requestId}` : undefined,
      duration: Infinity,
      closeButton: true,
    });
    return;
  }
  toast.error(fallback, { duration: Infinity, closeButton: true });
}
