// the query keys of this feature, in one place so invalidation can't miss one
export const seasonBoardKey = (season: string) => ["leaderboard", season] as const
export const gameBoardKey = (gameId: string) => ["leaderboard", "game", gameId] as const
