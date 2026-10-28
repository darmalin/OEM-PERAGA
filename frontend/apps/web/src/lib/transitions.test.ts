import { describe, expect, it } from "vitest";

import { moves, nextStatus, type TmStatus } from "./transitions";

describe("Call status transitions", () => {
  const transitions: [TmStatus, boolean, TmStatus][] = [
    ["NEW", true, "ANSWER"], ["NEW", false, "NO_ANSWER"],
    ["ANSWER", true, "RECONTACTED"], ["ANSWER", false, "RETRY_NO_ANSWER"],
    ["NO_ANSWER", true, "RECONTACTED"], ["NO_ANSWER", false, "RETRY_NO_ANSWER"],
    ["RETRY_NO_ANSWER", true, "RECONTACTED"], ["RETRY_NO_ANSWER", false, "RETRY_NO_ANSWER"],
    ["RECONTACTED", true, "RECONTACTED"], ["RECONTACTED", false, "RECONTACTED"],
  ];
  it.each(transitions)("%s, answered %s -> %s", (current, answered, target) => {
    expect(nextStatus(current, answered)).toBe(target);
  });
  it("allows dragging Answer to Retry No Answer", () => {
    expect(moves("ANSWER")).toContainEqual({ to: "RETRY_NO_ANSWER", answered: false, moves: true });
  });
});
