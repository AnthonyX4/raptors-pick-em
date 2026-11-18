import { GameCard } from "@/features/games/components/GameCard"
import { useSeasonGames } from "@/features/games/hooks"
import { ErrorState } from "@/components/states"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useDocumentTitle } from "@/hooks/useDocumentTitle"

function GameList({ games, empty }: { games: React.ReactNode[]; empty: string }) {
  if (games.length === 0) return <p className="py-8 text-muted-foreground">{empty}</p>
  return <div className="flex flex-col gap-3">{games}</div>
}

export function GamesPage() {
  const { data, isPending, isError, refetch, isFetching } = useSeasonGames()
  useDocumentTitle("Games")

  let body: React.ReactNode
  if (isPending) {
    body = (
      <div role="status" aria-busy="true" className="flex flex-col gap-3">
        <span className="sr-only">Loading the schedule…</span>
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-[72px] w-full" />
        ))}
      </div>
    )
  } else if (isError) {
    body = <ErrorState what="the schedule" onRetry={() => void refetch()} retrying={isFetching} />
  } else {
    // the api sends oldest first, which suits what's coming; results read better newest first
    const upcoming = data.filter((game) => game.status !== "final")
    const finished = data.filter((game) => game.status === "final").reverse()
    body = (
      // once the season is over there is nothing to look ahead to, so open on the results
      <Tabs defaultValue={upcoming.length > 0 ? "upcoming" : "finished"}>
        <TabsList variant="line" className="h-auto gap-6 border-b border-border p-0 pb-3">
          <TabsTrigger value="upcoming" className="flex-none px-0 text-base font-bold tracking-wide uppercase">
            Upcoming ({upcoming.length})
          </TabsTrigger>
          <TabsTrigger value="finished" className="flex-none px-0 text-base font-bold tracking-wide uppercase">
            Finished ({finished.length})
          </TabsTrigger>
        </TabsList>
        <TabsContent value="upcoming" className="mt-6">
          <GameList
            games={upcoming.map((game) => <GameCard key={game.game_id} game={game} />)}
            empty="No games left on the schedule."
          />
        </TabsContent>
        <TabsContent value="finished" className="mt-6">
          <GameList
            games={finished.map((game) => <GameCard key={game.game_id} game={game} />)}
            empty="No games have been played yet."
          />
        </TabsContent>
      </Tabs>
    )
  }

  return (
    <section className="mx-auto max-w-5xl">
      <h1 className="font-display text-5xl leading-none font-bold tracking-wide uppercase">Games</h1>
      <div className="mt-8">{body}</div>
    </section>
  )
}
