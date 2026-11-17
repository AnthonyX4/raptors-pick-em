import { api } from "@/lib/api-client"
import type { components, operations } from "@/types/api"

export type Game = components["schemas"]["GameResponse"]
export type GameDetail = components["schemas"]["GameDetail"]
export type PlayerStat = components["schemas"]["PlayerGameStatResponse"]
export type Team = components["schemas"]["TeamResponse"]
type GamesPage = components["schemas"]["PaginatedGamesResponse"]
export type GamesQuery = NonNullable<operations["get_games_api_games_get"]["parameters"]["query"]>

export const fetchGames = (query: GamesQuery) => api.get<GamesPage>("/api/games", { query })

export const fetchGame = (gameId: string) => api.get<GameDetail>(`/api/games/${gameId}`)

// the whole schedule, oldest first. a season is about 80 games, but the playoffs can push it past
// the 100-per-page maximum, so keep asking while the api says there's more
export async function fetchAllGames(): Promise<Game[]> {
  const games: Game[] = []
  for (let skip = 0; ; skip = games.length) {
    const page = await fetchGames({ skip, limit: 100 })
    games.push(...page.games)
    if (!page.has_more || page.games.length === 0) return games
  }
}
