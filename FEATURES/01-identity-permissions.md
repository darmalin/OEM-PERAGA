# 01 Identity, Roles, Permissions, Scope

Spec §9. Rules in `BACKEND_RULES/security-permissions.md`.

## Data
`users`, `roles`, `permissions`, `role_permissions`, `user_role_assignments` (role + scope type + scope target), `teams`, `user_team_memberships`.

## Baseline roles
`SUPER_ADMIN`, `EXHIBITION_ADMIN`, `TELEMARKETING_MANAGER`, `TELEMARKETING_AGENT`, `GATE_SUPERVISOR`, `GATE_STAFF`. Roles are bundles of permissions; checks always run on permission + scope, never on role name.

## Permissions
Seed every permission listed in §9.1 (`exhibition.*`, `edition.*`, `visitor.*`, `telemarketing.*`, `registration.*`, `gate.*`, `report.*`, `user.manage`, `role.manage`, `audit_log.read`).

## Scopes
`EDITION`, `TEAM`, `OWNED`, `GATE`. Super Admin may hold cross-edition scope.

## Tasks
- [ ] Models + migration + seed (roles, permissions, role_permissions).
- [ ] Login / logout / current user (`GET /api/v1/auth/me` returns user, permissions, scopes, allowed editions).
- [ ] Session store in Redis, cookie flags, idle and absolute timeout, session rotation on login.
- [ ] CSRF token issue + check on unsafe methods.
- [ ] Login rate limit per IP and per account; lockout policy.
- [ ] Password reset by email (token single-use, short expiry).
- [ ] `require(permission)` dependency + scope resolver that every module uses to filter queries.
- [ ] User management screens: list, create, deactivate, assign roles with scope, team membership.
- [ ] Role management screen: view permission matrix per role (edit only with `role.manage`).
- [ ] Permission matrix tests: every endpoint x every baseline role, expected allow/deny.

## Acceptance criteria
- Telemarketing Agent sees only leads assigned to them unless team policy grants TEAM scope.
- Gate Staff can only scan on assigned gates/devices.
- `visitor.export` is separate from `visitor.read`.
- Hiding a menu is never the only protection: a direct API call without permission returns 403.
- Deactivated user sessions are invalidated immediately.
