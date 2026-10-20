# Frontend Testing Rules

| Layer | Tool | What |
|---|---|---|
| Unit | Vitest | Formatters, label maps, status-to-indicator mapping, filter param parsing, scanner provisional logic |
| Component | Vitest + Testing Library + MSW | Forms (validation, API error mapping, version conflict), ListView states (loading, empty, filtered empty, error, no access) |
| Accessibility | `@axe-core/playwright` | Every main screen in light and dark, zero serious violations |
| E2E | Playwright against the compose stack | Login, edition switch, import, assign, log call, verify, register, resend QR, scanner offline sync |
| Visual check | Playwright screenshots | Lead form and list at 375, 768, 1280 widths, light and dark |

## Rules
- MSW handlers are typed from `@ems/api`, so mocks break when the API changes.
- Test data uses obvious fake values (`Visitor 001`, `visitor001@example.test`). No real people from production data.
- Query elements by role and label (`getByRole('button', { name: 'Log Call' })`), which also checks accessibility.
- Keyboard path is part of E2E: open a lead from the list with arrows + Enter, save with `Ctrl+S`, close dialogs with Escape.
- A screen is done only after it has been run in the browser, every control clicked, console checked for errors, both themes and mobile width checked.
