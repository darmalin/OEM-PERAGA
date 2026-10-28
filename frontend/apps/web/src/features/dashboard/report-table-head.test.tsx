import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { emptyRow, REPORT_METRIC_GROUPS, TABLE_METRICS } from "./metrics";
import { RecapTable } from "./recap-table";

afterEach(cleanup);

describe("Shared report header groups", () => {
  it("includes every existing metric once, in the same order as the report and CSV", () => {
    expect(REPORT_METRIC_GROUPS.flatMap(group => group.metrics)).toEqual(TABLE_METRICS);
  });
  it.each([
    { name: "daily", keys: undefined, userColumns: false, identities: 1 },
    { name: "source", keys: [{ id: "source-1", label: "Website" }], userColumns: false, identities: 2 },
    { name: "user", keys: [{ id: "source-1", label: "Agent", group: "Sales", editions: "EXPO" }], userColumns: true, identities: 4 },
  ])("aligns both header rows with the data for $name reports", ({ keys, userColumns, identities }) => {
    render(<RecapTable title="Report" days={["2026-10-28"]} rows={[{ ...emptyRow("2026-10-28", keys ? "source-1" : null), added: 7, pending: 12 }]} keys={keys} keyHeader="Source" userColumns={userColumns} fileName="report" />);
    expect(screen.getByRole("columnheader", { name: "Lead Acquisition" })).toHaveAttribute("colspan", "7");
    expect(screen.getByRole("columnheader", { name: "Lead Validity" })).toHaveAttribute("colspan", "2");
    expect(screen.getByRole("columnheader", { name: "Attendance" })).toHaveAttribute("colspan", "5");
    expect(screen.getByRole("columnheader", { name: "Buyer Type" })).toHaveAttribute("colspan", "3");
    expect(screen.getByRole("columnheader", { name: "Date" })).toHaveAttribute("rowspan", "2");
    const table = screen.getByRole("table");
    expect(table.querySelectorAll("thead tr:nth-child(2) th")).toHaveLength(17);
    const row = table.querySelector("tbody tr")!;
    expect(row.children).toHaveLength(identities + 17);
    expect(table.querySelector("tfoot")).toHaveTextContent("Grand Total");
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeEnabled();
  });
});
