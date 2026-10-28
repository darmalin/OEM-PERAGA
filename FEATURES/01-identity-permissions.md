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

## Role order (owner request 2026-10-26)
Roles carry `sort_order` (1–9999). Every role list and the Add Role picker show them by it, highest access first: Super Admin 1, Exhibition Admin 2, Telemarketing Manager 3, Telemarketing Agent 4, Gate Supervisor 5, Gate Staff 6; new roles default to 100. Global role managers change it, with name and description, through `PATCH /roles/{id}` (the code never changes).

## Admin boundaries (fixed 2026-10-25)
Super Admin (global) is held by the development team. An Exhibition Admin manages users only inside their editions:
- **No role above your own:** granting or revoking a role needs every permission of that role in the caller's own full-scope access for that edition (globally for cross-edition grants). Else `403 ROLE_ABOVE_YOURS`. Closes the hole where an edition admin could make anyone, themselves included, Super Admin of their edition.
- **Roles are global:** creating a role or changing its permissions needs `role.manage` held globally; an edition-scoped grant of it is not enough.
- **Users:** the list and detail show users with a role in the caller's editions, plus users with no role yet; others are `404`. Detail shows only the assignments inside those editions. Renaming or deactivating needs every role of the user to sit inside those editions and within the caller's access, else `403 USER_OUTSIDE_SCOPE`.
- The Add Role form offers only roles within the caller's own permissions.
- Team members: adding or removing someone needs that user to be fully inside the caller's editions (as for editing users).
- System menu: `/auth/me` returns `global_permissions`. Health and Email Accounts show only to global holders; Roles is read-only unless `role.manage` is global. The System panel opens on the first page the user can see.
- Tests: `tests/test_admin_boundaries.py`.

## User management (owner request 2026-10-28)
- User detail (System > Users > user) has **Change Password** (new password typed twice; same rules as everywhere, minimum 8) and **Disable User** / **Enable User**.
- API: `PATCH /users/{id}` accepts `password` next to `full_name` and `is_active`. The password is never stored in the audit snapshot; a separate `password_change` audit entry records that it changed.
- Changing the password or disabling a user ends all of that user's sessions at once. Changing your own password signs you out too.
- You cannot disable yourself (`422`).
- The admin boundaries above apply: an Exhibition Admin cannot change the password of, or disable, a user with access outside their editions or above their own (`403 USER_OUTSIDE_SCOPE`).
- Tests: `tests/test_identity.py` (`test_admin_changes_password_and_ends_sessions`, weak passwords, permission and version checks).

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
