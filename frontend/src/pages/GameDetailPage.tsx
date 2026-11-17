import { Link, useParams } from "react-router"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api-client"
import { ChatRoom } from "@/features/chat/components/ChatRoom"
import { GamePicks } from "@/features/picks/components/GamePicks"
import { BoxScore } from "@/features/games/components/BoxScore"
import { GameHeader } from "@/features/games/components/GameHeader"
import { useGame } from "@/features/games/hooks"

export function GameDetailPage() {
  const { gameId = "" } = useParams()
  const { data: game, isPending, error } = useGame(gameId)

  if (isPending) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (error) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <section className="mx-auto max-w-5xl">
        <h1 className="font-display text-4xl leading-none font-bold tracking-wide uppercase">
          {notFound ? "Game not found" : "Couldn't load this game"}
        </h1>
        <p className="mt-3 text-muted-foreground">
          {notFound ? "There's no game with that id." : "Try refreshing the page."}{" "}
          <Link to="/games" className="text-white underline underline-offset-4">
            Back to the schedule
          </Link>
        </p>
      </section>
    )
  }

  return (
    // the game and its picks on the left, the chat beside them; below lg the chat follows them
    <div className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)_26rem] items-start gap-10 max-lg:grid-cols-1">
      <div className="space-y-10">
        <GameHeader game={game} />
        <GamePicks game={game} />
        <BoxScore game={game} />
      </div>
      <aside className="sticky top-6 max-lg:static">
        <ChatRoom gameId={game.game_id} />
      </aside>
    </div>
  )
}
