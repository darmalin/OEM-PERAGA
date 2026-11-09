import { describe, expect, it } from "vitest";

import { cleanAnswers } from "./questions";

describe("answers", () => {
  it("drops blanks before saving", () => {
    expect(
      cleanAnswers({
        topic: "  ",
        speakers: [{ name: "Siti", company: "" }, {}],
        own_contractor: { name: "" },
        vip_needed: false,
        plates: ["B 1 AB", ""],
      }),
    ).toEqual({ speakers: [{ name: "Siti" }], vip_needed: false, plates: ["B 1 AB"] });
    expect(cleanAnswers({})).toBeUndefined();
  });
});
