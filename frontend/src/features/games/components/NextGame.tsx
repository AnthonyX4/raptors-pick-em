import { Link } from "react-router"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, formatPeriod, formatScore } from "@/lib/format"
import { useNextGame } from "../hooks"
import { Countdown } from "./Countdown"
import { StatusBadge } from "./StatusBadge"

// the home page's hero: the live game if one is on, otherwise the next one
export function NextGame() {
  const { data: game, isPending, isError } = useNextGame()

  if (isPending) return <Skeleton className="h-64 w-full" />
  if (isError) {
    return <p className="text-sm text-muted-foreground">Couldn't load the next game. Try refreshing the page.</p>
  }
  if (!game) {
    return (
      <div className="rounded-md border border-border bg-card p-8">
        <h2 className="font-display text-3xl font-bold tracking-wide uppercase">No upcoming games</h2>
        <p className="mt-2 text-muted-foreground">The schedule is finished for now. Look back at how the season went.</p>
        <Button asChild variant="outline" className="mt-6 font-bold tracking-wide uppercase">
          <Link to="/games">See the season</Link>
        </Button>
      </div>
    )
  }

  const live = game.status === "live"
  return (
    <div className="rounded-md border border-border bg-gradient-to-br from-[#4a0b0e] to-card p-8 max-md:p-5">
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold tracking-wide uppercase">{live ? "Live now" : "Next game"}</span>
        <StatusBadge game={game} />
      </div>
      <h2 className="mt-4 font-display text-6xl leading-none font-bold tracking-wide uppercase max-md:text-4xl">
        {game.away_team.full_name} <span className="text-muted-foreground">@</span> {game.home_team.full_name}
      </h2>
      <p className="mt-4 text-lg">
        {live ? (
          <>
            <span className="font-display text-3xl font-bold tabular-nums">
              {formatScore(game.away_score, game.home_score)}
            </span>
            <span className="ml-3 text-muted-foreground">
              {[formatPeriod(game.period), game.game_clock].filter(Boolean).join(" ")}
            </span>
          </>
        ) : (
          <>
            {formatDateTime(game.tipoff_utc)}
            {game.picks_open && (
              <span className="ml-3 text-muted-foreground">
                tips off in <Countdown game={game} />
              </span>
            )}
          </>
        )}
      </p>
      <Button asChild size="lg" className="mt-8 font-bold tracking-wide uppercase">
        <Link to={`/games/${game.game_id}`}>{game.picks_open ? "Make your picks" : "View game"}</Link>
      </Button>
    </div>
  )
}
