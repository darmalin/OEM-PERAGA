import { describe, expect, it } from "vitest";

import { basePath, date, exhibitorIdOf, exhibitorRouteOf, money, routeOf, timeLeft } from "./lib";

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

  it("reads the order form pages", () => {
    const id = "0d6f1c1e-3a43-4a8e-9d0c-111111111111";
    expect(exhibitorRouteOf(`/e/${id}`)).toEqual({ page: "exhibitor", id });
    expect(exhibitorRouteOf(`/e/${id}/forms`)).toEqual({ page: "forms", id });
    expect(exhibitorRouteOf(`/e/${id}/forms/`)).toEqual({ page: "forms", id });
    expect(exhibitorRouteOf(`/e/${id}/forms/02a`)).toEqual({ page: "form", id, code: "02a" });
    expect(exhibitorRouteOf(`/e/${id}/forms/04/review`)).toEqual({ page: "review", id, code: "04" });
    expect(exhibitorRouteOf(`/e/${id}/forms/4`)).toBeNull();
    expect(exhibitorRouteOf(`/e/${id}/contract`)).toBeNull();
  });
});

describe("format", () => {
  it("formats money and dates", () => {
    expect(money("15000000.00", "IDR")).toBe("IDR 15,000,000");
    expect(money("1250.50", "USD")).toBe("USD 1,250.50");
    expect(date("2027-03-09")).toBe("09-03-2027");
  });

  it("counts days to a deadline", () => {
    const now = new Date(2027, 1, 20, 15, 30);
    expect(timeLeft("2027-02-25", now)).toBe("In 5 days");
    expect(timeLeft("2027-02-21", now)).toBe("Tomorrow");
    expect(timeLeft("2027-02-20", now)).toBe("Today");
    expect(timeLeft("2027-02-19", now)).toBe("Past");
    expect(timeLeft(null, now)).toBe("");
  });
});
