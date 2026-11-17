import type { Pick, PickWithUser } from "./api"

// a pick's answer as text: the team, the margin or the player, whichever its category's kind filled in
export function answerText(pick: Pick | PickWithUser): string {
  if (pick.team) return pick.team.full_name
  if (pick.player) return pick.player.full_name
  if (pick.margin !== null) return `${pick.margin} ${pick.margin === 1 ? "point" : "points"}`
  return "–"
}

// null until the game is scored
export function pointsText(points: number | null): string {
  if (points === null) return "Pending"
  return `${points} ${points === 1 ? "pt" : "pts"}`
}

// the sum of what has been awarded so far, or null if nothing has been scored
export function totalPoints(picks: { points_awarded: number | null }[]): number | null {
  const scored = picks.filter((pick) => pick.points_awarded !== null)
  return scored.length === 0 ? null : scored.reduce((sum, pick) => sum + (pick.points_awarded ?? 0), 0)
}
