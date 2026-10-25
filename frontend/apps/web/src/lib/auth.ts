import { api, call, setCsrfToken, type Schemas } from "@ems/api";
import { queryOptions, useQuery } from "@tanstack/react-query";

export type Me = Schemas["MeOut"];

export const meQuery = queryOptions({
  queryKey: ["auth", "me"],
  queryFn: async (): Promise<Me> => {
    const me = await call(api.GET("/api/v1/auth/me"));
    setCsrfToken(me.csrf_token);
    return me;
  },
  staleTime: 60_000,
  retry: false,
});

export function useMe(): Me {
  const { data } = useQuery(meQuery);
  if (!data) throw new Error("useMe outside an authenticated route");
  return data;
}

/** UX only: hides what the user cannot use. The backend enforces every permission. */
export function can(me: Me, ...permissions: string[]): boolean {
  return permissions.some((p) => me.permissions.includes(p));
}

/** Held across every edition (Super Admin): platform pages and global objects like roles. */
export function canGlobal(me: Me, ...permissions: string[]): boolean {
  return permissions.some((p) => (me.global_permissions ?? []).includes(p));
}
