import { ErrorState, Loading } from "@/components/states"
import type { GameDetail } from "@/features/games/api"
import { answerText, pointsText, totalPoints } from "../answer"
import { useMyPicks } from "../hooks"

// your own picks, read-only: once the game has started, or while it's postponed
export function MyPicks({ game }: { game: GameDetail }) {
  const { data: picks, isPending, isError, refetch, isFetching } = useMyPicks(game.game_id, game.status)

  let body: React.ReactNode
  if (isPending) {
    body = <Loading what="your picks" className="h-24 w-full" />
  } else if (isError) {
    body = <ErrorState what="your picks" onRetry={() => void refetch()} retrying={isFetching} />
  } else if (picks.length === 0) {
    body = <p className="text-muted-foreground">You didn't make any picks for this game.</p>
  } else {
    const total = totalPoints(picks)
    body = (
      <ul className="divide-y divide-border rounded-md border border-border bg-card">
        {picks.map((pick) => (
          <li key={pick.pick_id} className="flex items-center justify-between gap-4 px-5 py-3">
            <div className="min-w-0">
              <div className="text-sm text-muted-foreground">{pick.category.name}</div>
              <div className="font-bold">{answerText(pick)}</div>
            </div>
            <div className={pick.points_awarded ? "font-bold" : "text-muted-foreground"}>
              {pointsText(pick.points_awarded)}
            </div>
          </li>
        ))}
        {total !== null && (
          <li className="flex items-center justify-between px-5 py-3 font-display text-xl font-bold tracking-wide uppercase">
            <span>Total</span>
            <span>{pointsText(total)}</span>
          </li>
        )}
      </ul>
    )
  }

  return (
    <section>
      <h2 className="mb-4 font-display text-3xl font-bold tracking-wide uppercase">Your picks</h2>
      {game.status === "postponed" && picks && picks.length > 0 && (
        <p className="mb-4 text-sm text-muted-foreground">Your picks are kept for when the game is rescheduled.</p>
      )}
      {body}
    </section>
  )
}
