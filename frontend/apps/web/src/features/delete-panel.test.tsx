import { ApiError } from "@ems/api";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { forgetEdition } from "@/lib/edition";

import { DeletePanel } from "./delete-panel";

const notify = vi.hoisted(() => ({ notifyError: vi.fn() }));
vi.mock("@/lib/notify", () => notify);
afterEach(() => { cleanup(); notify.notifyError.mockReset(); localStorage.clear(); });

function show(onDelete: () => Promise<void>, onStale = vi.fn()) {
  render(<DeletePanel title="Delete Edition" description="Only empty editions." confirmText="Permanently delete IBTE2027?" onDelete={onDelete} onStale={onStale} />);
  return { user: userEvent.setup(), onStale };
}

describe("DeletePanel", () => {
  it("asks before deleting", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    const { user } = show(onDelete);
    await user.click(screen.getByRole("button", { name: "Delete Edition" }));
    expect(onDelete).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Delete Edition" }));
    await user.click(screen.getByRole("button", { name: "Confirm Delete" }));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("shows what still links to the record when the delete is blocked", async () => {
    const blocked = new ApiError(409, { error: { code: "EDITION_IN_USE", message: "This edition still has 3 booths, 1 exhibitor lead." } });
    const { user } = show(vi.fn().mockRejectedValue(blocked));
    await user.click(screen.getByRole("button", { name: "Delete Edition" }));
    await user.click(screen.getByRole("button", { name: "Confirm Delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("3 booths, 1 exhibitor lead");
    expect(notify.notifyError).not.toHaveBeenCalled();
  });

  it("reloads the record on a version conflict", async () => {
    const stale = new ApiError(409, { error: { code: "VERSION_CONFLICT", message: "Changed." } });
    const { user, onStale } = show(vi.fn().mockRejectedValue(stale));
    await user.click(screen.getByRole("button", { name: "Delete Edition" }));
    await user.click(screen.getByRole("button", { name: "Confirm Delete" }));
    expect(onStale).toHaveBeenCalledOnce();
    expect(notify.notifyError).toHaveBeenCalledWith(stale);
  });
});

describe("forgetEdition", () => {
  it("clears the saved edition only when it is the deleted one", () => {
    localStorage.setItem("ems.edition", "keep");
    forgetEdition("gone");
    expect(localStorage.getItem("ems.edition")).toBe("keep");
    forgetEdition("keep");
    expect(localStorage.getItem("ems.edition")).toBeNull();
  });
});
