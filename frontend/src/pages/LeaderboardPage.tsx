import { ErrorState, Loading } from "@/components/states"
import { useSeasonGames } from "@/features/games/hooks"
import { currentSeason } from "@/features/games/season"
import { LeaderboardTable } from "@/features/leaderboard/components/LeaderboardTable"
import { useSeasonBoard } from "@/features/leaderboard/hooks"
import { useDocumentTitle } from "@/hooks/useDocumentTitle"

export function LeaderboardPage() {
  // the season comes from the schedule, which the games page has usually cached already
  useDocumentTitle("Leaderboard")
  const games = useSeasonGames()
  const season = games.data ? currentSeason(games.data) : null
  const board = useSeasonBoard(season)
  const entries = board.data?.pages.flatMap((page) => page.entries) ?? []

  let body: React.ReactNode
  if (games.isPending || (season !== null && board.isPending)) {
    body = <Loading what="the standings" className="h-64 w-full" />
  } else if (games.isError || board.isError) {
    // ask again for whichever of the two failed
    const failed = games.isError ? games : board
    body = <ErrorState what="the standings" onRetry={() => void failed.refetch()} retrying={failed.isFetching} />
  } else if (entries.length === 0) {
    body = <p className="text-muted-foreground">No scores yet. Standings appear once the first game is scored.</p>
  } else {
    body = (
      <LeaderboardTable
        entries={entries}
        hasMore={board.hasNextPage}
        loadingMore={board.isFetchingNextPage}
        onLoadMore={() => void board.fetchNextPage()}
      />
    )
  }

  return (
    <section className="mx-auto max-w-4xl">
      <h1 className="font-display text-5xl leading-none font-bold tracking-wide uppercase">Leaderboard</h1>
      <p className="mt-3 text-muted-foreground">
        {season ? `${season} season. ` : ""}Only scored games count. Tied totals share a rank.
      </p>
      <div className="mt-8">{body}</div>
    </section>
  )
}
