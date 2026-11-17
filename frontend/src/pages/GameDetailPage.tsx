import { Link, useParams } from "react-router"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api-client"
import { BoxScore } from "@/features/games/components/BoxScore"
import { GameHeader } from "@/features/games/components/GameHeader"
import { useGame } from "@/features/games/hooks"

// picks (16.4) and chat (16.5) will sit beside and below the game
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
    <div className="mx-auto max-w-5xl space-y-10">
      <GameHeader game={game} />
      <BoxScore game={game} />
    </div>
  )
}
