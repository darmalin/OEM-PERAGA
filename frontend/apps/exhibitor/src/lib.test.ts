import { describe, expect, it } from "vitest";

import { basePath, date, exhibitorIdOf, money, routeOf } from "./lib";

describe("portal routes", () => {
  it("works under /exhibitor and on its own host", () => {
    expect(basePath("/exhibitor/accept-invite")).toBe("/exhibitor");
    expect(basePath("/exhibitor")).toBe("/exhibitor");
    expect(basePath("/exhibitors-old")).toBe("");
    expect(routeOf("/exhibitor/accept-invite")).toBe("/accept-invite");
    expect(routeOf("/exhibitor/")).toBe("/");
    expect(routeOf("/exhibitor")).toBe("/");
    expect(routeOf("/login")).toBe("/login");
  });

  it("reads the exhibitor id", () => {
    expect(exhibitorIdOf("/e/0d6f1c1e-3a43-4a8e-9d0c-111111111111")).toBe("0d6f1c1e-3a43-4a8e-9d0c-111111111111");
    expect(exhibitorIdOf("/e/not-an-id")).toBeNull();
  });
});

describe("format", () => {
  it("formats money and dates", () => {
    expect(money("15000000.00", "IDR")).toBe("IDR 15,000,000");
    expect(money("1250.50", "USD")).toBe("USD 1,250.50");
    expect(date("2027-03-09")).toBe("09-03-2027");
  });
});
