import { api } from "@/lib/api-client"
import type { components } from "@/types/api"
import type { SaveStep } from "./schema"

export type Category = components["schemas"]["PickCategoryResponse"]
export type Pick = components["schemas"]["PickResponse"]
export type PickWithUser = components["schemas"]["PickWithUser"]
export type Player = components["schemas"]["PlayerResponse"]
type PicksPage = components["schemas"]["PaginatedPicksResponse"]
type GamePicksPage = components["schemas"]["PaginatedGamePicksResponse"]
type PlayersPage = components["schemas"]["PaginatedPlayersResponse"]

export const fetchCategories = () => api.get<Category[]>("/api/pick-categories")

// one page is enough: a roster is about 17 players and the page maximum is 100
export const fetchRoster = async (tricode: string) =>
  (await api.get<PlayersPage>("/api/players", { query: { team: tricode, limit: 100 } })).players

// a game has one pick per category, so a user's picks for it fit in one page
export const fetchMyPicks = async (gameId: string) =>
  (await api.get<PicksPage>("/api/picks/me", { query: { game_id: gameId, limit: 100 } })).picks

export const fetchGamePicks = (gameId: string, skip: number) =>
  api.get<GamePicksPage>("/api/picks", { query: { game_id: gameId, skip, limit: 100 } })

// one request of a save, see planSave
export async function runStep(step: SaveStep, gameId: string): Promise<void> {
  if (step.type === "create") {
    await api.post<Pick>("/api/picks", { game_id: gameId, pick_category_id: step.categoryId, ...step.body })
  } else if (step.type === "update") {
    await api.patch<Pick>(`/api/picks/${step.pickId}`, step.body)
  } else {
    await api.delete(`/api/picks/${step.pickId}`)
  }
}
