import { describe, expect, it } from "vitest";

import { tokenFromPath } from "./api";
import { formatDate, strings } from "./i18n";
import { readUtm } from "./tracking";

describe("campaign form helpers", () => {
  it("reads the token from /{token} or /r/{token} only", () => {
    expect(tokenFromPath("/r/AbC_d-12xyZ9")).toBe("AbC_d-12xyZ9");
    expect(tokenFromPath("/r/AbC_d-12xyZ9/")).toBe("AbC_d-12xyZ9");
    expect(tokenFromPath("/AbC_d-12xyZ9")).toBe("AbC_d-12xyZ9");
    expect(tokenFromPath("/r/")).toBeNull();
    expect(tokenFromPath("/")).toBeNull();
    expect(tokenFromPath("/r/a/b")).toBeNull();
    expect(tokenFromPath("/r/%3Cscript%3E")).toBeNull();
    expect(tokenFromPath("/app/visitor-leads")).toBeNull();
  });

  it("keeps only the five UTM tags, trimmed and capped", () => {
    const utm = readUtm(`?utm_source=%20instagram%20&utm_medium=story&gclid=x&email=a@b.c&utm_term=${"x".repeat(300)}`);
    expect(utm).toEqual({ utm_source: "instagram", utm_medium: "story", utm_term: "x".repeat(200) });
  });

  it("speaks both languages with the same keys", () => {
    expect(Object.keys(strings("id")).sort()).toEqual(Object.keys(strings("en")).sort());
    expect(strings("id").submit).toBe("Daftar");
    expect(formatDate("2027-03-10", "id")).toContain("Maret");
    expect(formatDate("2027-03-10", "en")).toContain("March");
  });
});
