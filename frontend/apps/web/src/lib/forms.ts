import { ApiError } from "@ems/api";
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { notifyError } from "./notify";

/** Put API 409/422 field errors under their fields, and the message in a toast. */
export function handleFormError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  known: readonly string[],
): void {
  if (error instanceof ApiError) {
    for (const [field, message] of Object.entries(error.fields)) {
      const name = field.split(".")[0] ?? field;
      if (known.includes(name)) setError(name as Path<T>, { type: "server", message });
    }
  }
  notifyError(error);
}

/** Drop empty strings so optional fields are sent as absent, not "". */
export function compact<T extends Record<string, unknown>>(values: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(values).filter(([, v]) => v !== "" && v !== undefined),
  ) as Partial<T>;
}

export function uuid(): string {
  return crypto.randomUUID();
}
