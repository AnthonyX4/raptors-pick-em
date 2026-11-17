// the query keys of this feature, in one place so invalidation can't miss one
export const chatKey = (gameId: string) => ["chat", gameId] as const
