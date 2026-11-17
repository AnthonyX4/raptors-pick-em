import { useQuery } from "@tanstack/react-query"
import { fetchAllGames, fetchGame, fetchGames, type Game } from "./api"
import { gameKey, gamesKey } from "./keys"

// the poller's own cadence while a game is on
const LIVE_REFRESH_MS = 30_000

// refetch while the score is moving, and while a game is "starting": tipoff has passed but the poller
// hasn't flipped it to live yet. both come from the api's fields, not from the clock
function refreshInterval(game: Game | null | undefined) {
  if (!game) return false
  const starting = game.status === "scheduled" && !game.picks_open
  return game.status === "live" || starting ? LIVE_REFRESH_MS : false
}

export const useGame = (gameId: string) =>
  useQuery({
    queryKey: gameKey(gameId),
    queryFn: () => fetchGame(gameId),
    refetchInterval: (query) => refreshInterval(query.state.data),
  })

// the oldest game that isn't final: the live one if a game is on. null in the off-season
export const useNextGame = () =>
  useQuery({
    queryKey: gamesKey({ upcoming: true, limit: 1 }),
    queryFn: async () => (await fetchGames({ upcoming: true, limit: 1 })).games[0] ?? null,
    refetchInterval: (query) => refreshInterval(query.state.data),
  })

export const useSeasonGames = () => useQuery({ queryKey: gamesKey({ all: true }), queryFn: fetchAllGames })
