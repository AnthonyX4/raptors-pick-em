// the query keys of this feature, in one place so invalidation can't miss one
export const allGamesKey = ["games"] as const // every games list, whatever its filters
export const gamesKey = (filters: object = {}) => ["games", filters] as const
export const gameKey = (gameId: string) => ["game", gameId] as const
