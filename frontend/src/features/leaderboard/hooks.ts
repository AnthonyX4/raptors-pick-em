import { useInfiniteQuery } from "@tanstack/react-query"
import { fetchGameBoard, fetchSeasonBoard, type LeaderboardPage } from "./api"
import { gameBoardKey, seasonBoardKey } from "./keys"

const getNextSkip = (last: LeaderboardPage) => (last.has_more ? last.skip + last.entries.length : undefined)

// season standings. waits for a season: it comes from the schedule (see currentSeason)
export const useSeasonBoard = (season: string | null) =>
  useInfiniteQuery({
    queryKey: seasonBoardKey(season ?? ""),
    queryFn: ({ pageParam }) => fetchSeasonBoard(season ?? "", pageParam),
    initialPageParam: 0,
    getNextPageParam: getNextSkip,
    enabled: season !== null,
  })

// one finished game's standings. scoring follows the final buzzer by a short while, so an empty board is
// asked for again every 30 seconds until it has someone on it
export const useGameBoard = (gameId: string) =>
  useInfiniteQuery({
    queryKey: gameBoardKey(gameId),
    queryFn: ({ pageParam }) => fetchGameBoard(gameId, pageParam),
    initialPageParam: 0,
    getNextPageParam: getNextSkip,
    refetchInterval: (query) => (query.state.data?.pages[0]?.entries.length === 0 ? 30_000 : false),
  })
