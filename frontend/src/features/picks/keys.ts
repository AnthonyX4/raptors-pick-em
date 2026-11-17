// the query keys of this feature, in one place so invalidation can't miss one
export const categoriesKey = ["pick-categories"] as const
export const rosterKey = (tricode: string) => ["players", tricode] as const
export const myPicksKey = (gameId: string) => ["picks", "me", gameId] as const
export const gamePicksKey = (gameId: string) => ["picks", "game", gameId] as const
