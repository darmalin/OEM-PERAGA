import { ApiError } from "@ems/api";
import type { QueryClient } from "@tanstack/react-query";
import { redirect } from "@tanstack/react-router";

import { type Me, meQuery } from "./auth";

/** Route guard: load the session or send the user to the sign-in page. */
export async function requireMe(queryClient: QueryClient, href: string): Promise<Me> {
  try {
    return await queryClient.ensureQueryData(meQuery);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      throw redirect({ to: "/login", search: { next: href } });
    }
    throw e;
  }
}
