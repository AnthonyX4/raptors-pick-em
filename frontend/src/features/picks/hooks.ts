import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { allGamesKey, gameKey } from "@/features/games/keys"
import { ApiError } from "@/lib/api-client"
import { FOLLOWED_TEAM } from "@/lib/constants"
import { fetchCategories, fetchGamePicks, fetchMyPicks, fetchRoster, runStep } from "./api"
import { categoriesKey, gamePicksKey, myPicksKey, rosterKey } from "./keys"
import type { SaveStep } from "./schema"

const REFRESH_MS = 30_000

// while a game is on, or has finished but isn't scored yet, points_awarded changes under the reader
function refreshWhile(status: string, picks: { points_awarded: number | null }[]) {
  const scoring = status === "final" && picks.some((pick) => pick.points_awarded === null)
  return status === "live" || scoring ? REFRESH_MS : false
}

// categories and rosters change rarely: an admin edit or a trade
const RARELY = 5 * 60_000

export const useCategories = () =>
  useQuery({ queryKey: categoriesKey, queryFn: fetchCategories, staleTime: RARELY })

export const useRoster = () =>
  useQuery({ queryKey: rosterKey(FOLLOWED_TEAM), queryFn: () => fetchRoster(FOLLOWED_TEAM), staleTime: RARELY })

export const useMyPicks = (gameId: string, status: string) =>
  useQuery({
    queryKey: myPicksKey(gameId),
    queryFn: () => fetchMyPicks(gameId),
    refetchInterval: (query) => refreshWhile(status, query.state.data ?? []),
  })

// everyone's picks, only to be asked for once the game has started: before that the api answers 403
export const useGamePicks = (gameId: string, status: string) =>
  useInfiniteQuery({
    queryKey: gamePicksKey(gameId),
    queryFn: ({ pageParam }) => fetchGamePicks(gameId, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.has_more ? last.skip + last.picks.length : undefined),
    refetchInterval: (query) => refreshWhile(status, query.state.data?.pages.flatMap((page) => page.picks) ?? []),
  })

// saving is one request per changed category (see planSave), in an order the backend's rules allow. it
// stops at the first failure and refetches either way: the server's picks are the truth, not the form's
export function useSavePicks(gameId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (steps: SaveStep[]) => {
      for (const step of steps) await runStep(step, gameId)
    },
    onError: (error) => {
      // a 409 can mean the picks just locked at tipoff: ask the server for the game again so the page says so
      if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: gameKey(gameId) })
        void queryClient.invalidateQueries({ queryKey: allGamesKey })
      }
    },
    // returned so the mutation settles after the refetch, when the form can be reseeded
    onSettled: () => queryClient.invalidateQueries({ queryKey: myPicksKey(gameId) }),
  })
}
