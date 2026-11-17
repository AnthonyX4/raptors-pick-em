import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

export type LeaderboardEntry = components["schemas"]["LeaderboardEntry"]
export type LeaderboardPage = components["schemas"]["LeaderboardResponse"]

const PAGE_SIZE = 50

// ranks come from the api (tied totals share one) and stay true across pages, so pages are just appended
export const fetchSeasonBoard = (season: string, skip: number) =>
  api.get<LeaderboardPage>("/api/leaderboard", { query: { season, skip, limit: PAGE_SIZE } })

// empty until the game has been scored
export const fetchGameBoard = (gameId: string, skip: number) =>
  api.get<LeaderboardPage>(`/api/leaderboard/games/${gameId}`, { query: { skip, limit: PAGE_SIZE } })
