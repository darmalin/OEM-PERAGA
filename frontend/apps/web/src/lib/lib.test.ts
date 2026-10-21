import { describe, expect, it } from "vitest";

import { eventCountdown, fromLocalInput, toLocalInput } from "./format";
import { label, options } from "./labels";
import { toneFor } from "./status";

describe("labels", () => {
  it("shows the team's labels, never raw codes", () => {
    expect(label("attend", "ATTEND_SOURCING")).toBe("Attend Sourcing");
    expect(label("buyer_type", "B_SIDE")).toBe("B-Side");
    expect(label("telemarketing_status", "RETRY_NO_ANSWER")).toBe("Retry No Answer");
    expect(label("source", null)).toBe("");
  });

  it("keeps the five Attend options in spec order", () => {
    expect(options("attend").map((o) => o.label)).toEqual([
      "Attend",
      "Attend Sourcing",
      "Under Consideration",
      "Not Attend",
      "Hang Up Immediately",
    ]);
  });
});

describe("status tones", () => {
  it("gives every status one color", () => {
    expect(toneFor("FIRST_ENTRY")).toBe("green");
    expect(toneFor("REPEAT_ENTRY")).toBe("amber");
    expect(toneFor("REJECTED_WRONG_EDITION")).toBe("red");
    expect(toneFor("SOMETHING_NEW")).toBe("gray");
  });
});

describe("event-local time", () => {
  it("round-trips a datetime-local value through the edition timezone", () => {
    const iso = fromLocalInput("2027-03-10T09:30", "Asia/Jakarta");
    expect(iso).toBe("2027-03-10T02:30:00.000Z");
    expect(toLocalInput(iso, "Asia/Jakarta")).toBe("2027-03-10T09:30");
  });

  it("describes the event relative to today", () => {
    expect(eventCountdown("2999-01-01", "2999-01-03", "UTC")).toMatch(/^Opens in \d+ days$/);
    expect(eventCountdown("2000-01-01", "2000-01-03", "UTC")).toMatch(/^Ended \d+ days ago$/);
  });
});
