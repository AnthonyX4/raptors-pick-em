import { Skeleton } from "@/components/ui/skeleton"
import { useGameBoard } from "../hooks"
import { LeaderboardTable } from "./LeaderboardTable"

// how everyone did in one finished game. mounted only for a final game
export function GameLeaderboard({ gameId }: { gameId: string }) {
  const board = useGameBoard(gameId)
  const entries = board.data?.pages.flatMap((page) => page.entries) ?? []

  let body: React.ReactNode
  if (board.isPending) {
    body = <Skeleton className="h-32 w-full" />
  } else if (board.isError) {
    body = <p className="text-sm text-muted-foreground">Couldn't load the standings. Try refreshing the page.</p>
  } else if (entries.length === 0) {
    // picks are scored a little after the final buzzer; this asks again until they are
    body = <p className="text-muted-foreground">No scores yet. Picks are scored shortly after the game ends.</p>
  } else {
    body = (
      <LeaderboardTable
        entries={entries}
        hasMore={board.hasNextPage}
        loadingMore={board.isFetchingNextPage}
        onLoadMore={() => void board.fetchNextPage()}
        showGames={false}
      />
    )
  }

  return (
    <section>
      <h2 className="mb-4 font-display text-3xl font-bold tracking-wide uppercase">Game standings</h2>
      {body}
    </section>
  )
}
