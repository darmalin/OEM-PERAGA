import { api, call, type Schemas } from "@ems/api";
import { queryOptions } from "@tanstack/react-query";

export const teamQuery = (teamId: string) => queryOptions({ queryKey: ["team", teamId], queryFn: () => call(api.GET("/api/v1/teams/{team_id}", { params: { path: { team_id: teamId } } })) });
export const teamUsersQuery = queryOptions({
  queryKey: ["users", "team-members"],
  queryFn: async () => {
    const users: Schemas["UserOut"][] = [];
    for (let page = 1; ; page++) {
      const result = await call(api.GET("/api/v1/users", { params: { query: { page, page_size: 500 } } }));
      users.push(...result.items);
      if (!result.items.length || users.length >= result.total) return users;
    }
  },
});

export const teamMemberOptionsQuery = queryOptions({
  queryKey: ["team-member-options"],
  queryFn: async () => {
    const users: Schemas["UserOut"][] = [];
    for (let page = 1; ; page++) {
      const result = await call(api.GET("/api/v1/teams/member-options", { params: { query: { page, page_size: 500 } } }));
      users.push(...result.items);
      if (!result.items.length || users.length >= result.total) return users;
    }
  },
});
