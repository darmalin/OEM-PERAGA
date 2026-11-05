import type { ExhibitorLead, SalesStage } from "./queries";

/** How a board move happens: the stage API at once, or a page that asks for more first. */
export type BoardMove =
  | { to: SalesStage; kind: "direct" }
  | { to: SalesStage; kind: "stage-page" }
  | { to: SalesStage; kind: "booth-page" }
  | { to: SalesStage; kind: "convert-page" };

/** Moves offered for a card. Only moves with no side effect happen at once; Lost needs a reason,
 * leaving Opportunity releases a held booth, and becoming an Exhibitor is Convert. */
export function boardMoves(lead: Pick<ExhibitorLead, "stage" | "booth_id">, perms: { update: boolean; invite: boolean }): BoardMove[] {
  if (!perms.update) return [];
  switch (lead.stage) {
    case "LEAD":
      return [{ to: "OPPORTUNITY", kind: "direct" }, { to: "LOST", kind: "stage-page" }];
    case "OPPORTUNITY": {
      const moves: BoardMove[] = [
        { to: "LEAD", kind: lead.booth_id ? "stage-page" : "direct" },
        { to: "LOST", kind: "stage-page" },
      ];
      if (perms.invite) moves.push({ to: "EXHIBITOR", kind: lead.booth_id ? "convert-page" : "booth-page" });
      return moves;
    }
    case "LOST":
      return [{ to: "LEAD", kind: "direct" }];
    default:
      return [];
  }
}
