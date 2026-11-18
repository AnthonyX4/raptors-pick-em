// the query keys of this feature, in one place so invalidation can't miss one
export const userKey = (userId: number) => ["user", userId] as const
