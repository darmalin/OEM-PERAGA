import { describe, expect, it } from "vitest";

import { boardMoves } from "./board-moves";

const all = { update: true, invite: true };

describe("exhibitor board moves", () => {
  it("moves at once only without side effects", () => {
    expect(boardMoves({ stage: "LEAD", booth_id: null }, all)).toEqual([
      { to: "OPPORTUNITY", kind: "direct" },
      { to: "LOST", kind: "stage-page" },
    ]);
    expect(boardMoves({ stage: "LOST", booth_id: null }, all)).toEqual([{ to: "LEAD", kind: "direct" }]);
    expect(boardMoves({ stage: "EXHIBITOR", booth_id: "b" }, all)).toEqual([]);
  });

  it("asks before releasing a booth and converts through its page", () => {
    expect(boardMoves({ stage: "OPPORTUNITY", booth_id: "b" }, all)).toEqual([
      { to: "LEAD", kind: "stage-page" },
      { to: "LOST", kind: "stage-page" },
      { to: "EXHIBITOR", kind: "convert-page" },
    ]);
    expect(boardMoves({ stage: "OPPORTUNITY", booth_id: null }, all).map((m) => m.kind)).toEqual(["direct", "stage-page", "booth-page"]);
  });

  it("follows permissions", () => {
    expect(boardMoves({ stage: "LEAD", booth_id: null }, { update: false, invite: true })).toEqual([]);
    expect(boardMoves({ stage: "OPPORTUNITY", booth_id: "b" }, { update: true, invite: false }).map((m) => m.to)).toEqual(["LEAD", "LOST"]);
  });
});
