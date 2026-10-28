import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { emptyRow } from "./metrics";
import { answeredCalls, changeLabel, previousPeriod, unansweredCalls } from "./overview";
import { SourceDetail } from "./source-detail";

afterEach(cleanup);

describe("Dashboard calculations", () => {
  it("compares equal-length adjacent periods across month and leap-day boundaries", () => {
    expect(previousPeriod("2026-09-29", "2026-10-28")).toEqual({ from: "2026-08-30", to: "2026-09-28" });
    expect(previousPeriod("2024-02-29", "2024-02-29")).toEqual({ from: "2024-02-28", to: "2024-02-28" });
    expect(previousPeriod("2024-02-01", "2024-02-29")).toEqual({ from: "2024-01-03", to: "2024-01-31" });
  });
  it("never invents a percentage when the previous period has no records", () => {
    expect(changeLabel(12, 0)).toBe("New in period");
    expect(changeLabel(0, 0)).toBe("No change");
    expect(changeLabel(120, 100)).toBe("20%");
    expect(changeLabel(75, 100)).toBe("25%");
  });
  it("includes repeat calls in response totals", () => {
    const row = { ...emptyRow(), answer: 10, recontacted: 3, non_answer: 4, retry_no_answer: 2 };
    expect(answeredCalls(row)).toBe(13);
    expect(unansweredCalls(row)).toBe(6);
  });
});

it("expands sources by date and keeps the authoritative period Pending total", async () => {
  const first = { ...emptyRow("2026-09-29"), added: 5, pending: 10 };
  const second = { ...emptyRow("2026-09-30"), added: 7, pending: 15 };
  render(<SourceDetail from="2026-09-29" to="2026-09-30" daily={[first, second]} total={{ ...emptyRow(), added: 12, pending: 15 }} rows={[{ ...first, key: "source-1" }]} sources={[{ id: "source-1", label: "Website" }]} />);
  expect(screen.getByRole("columnheader", { name: "Lead Acquisition" })).toHaveAttribute("colspan", "5");
  const grand = screen.getByRole("rowheader", { name: "Grand Total" }).closest("tr")!;
  expect(within(grand).getAllByRole("cell")[1]).toHaveTextContent("15");
  expect(screen.getByRole("rowheader", { name: "Website" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Collapse 29 Sep (Tue)" }));
  expect(screen.queryByRole("rowheader", { name: "Website" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Expand 29 Sep (Tue)" }));
  expect(screen.getByRole("rowheader", { name: "Website" })).toBeVisible();
});

it("allows every date to expand and collapse even when no breakdown rows exist", async () => {
  render(<SourceDetail from="2026-10-01" to="2026-10-02" daily={[]} total={emptyRow()} rows={[]} sources={[]} />);
  expect(screen.getByRole("button", { name: "Collapse 1 Oct (Thu)" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Expand 2 Oct (Fri)" }));
  expect(screen.getByRole("button", { name: "Collapse 2 Oct (Fri)" })).toHaveAttribute("aria-expanded", "true");
  expect(screen.getAllByText("No detail is recorded for this date and the selected filters.")).toHaveLength(2);
  await userEvent.click(screen.getByRole("button", { name: "Collapse 2 Oct (Fri)" }));
  expect(screen.getByRole("button", { name: "Expand 2 Oct (Fri)" })).toHaveAttribute("aria-expanded", "false");
});

 it("shows every source with a count only on its corresponding date", async () => {
  const first = { ...emptyRow("2026-09-29"), added: 3 };
  const second = { ...emptyRow("2026-09-30"), total: 2, answer: 2 };
  render(<SourceDetail from="2026-09-29" to="2026-09-30" daily={[first, second]} total={emptyRow()} rows={[{ ...first, key: "a" }, { ...first, key: "b", added: 0, pending: 4 }, { ...second, key: "c" }, { ...emptyRow("2026-09-29"), key: "zero" }]} sources={[{ id: "a", label: "Website" }, { id: "b", label: "Facebook" }, { id: "c", label: "On site" }, { id: "zero", label: "Empty source" }]} />);
  expect(screen.getByRole("rowheader", { name: "Website" })).toBeVisible();
  expect(screen.getByRole("rowheader", { name: "Facebook" })).toBeVisible();
  expect(screen.queryByRole("rowheader", { name: "Empty source" })).not.toBeInTheDocument();
  expect(screen.queryByRole("rowheader", { name: "On site" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Expand 30 Sep (Wed)" }));
  expect(screen.getByRole("rowheader", { name: "On site" })).toBeVisible();
});
