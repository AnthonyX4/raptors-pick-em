import type { Game } from "./api"

// the api has no "current season", so it is read off the schedule: the season of the first game that isn't
// over (the oldest first, so that's the one being played), or of the last game once the season is done.
// null for an empty schedule
export function currentSeason(games: Pick<Game, "season" | "status">[]): string | null {
  const upcoming = games.find((game) => game.status !== "final")
  return (upcoming ?? games.at(-1))?.season ?? null
}
