import { MapPin } from "lucide-react"
import { formatDateTime, formatPeriod } from "@/lib/format"
import type { Game, Team } from "../api"
import { Countdown } from "./Countdown"
import { StatusBadge } from "./StatusBadge"

function TeamBlock({ team, score, align }: { team: Team; score: number | null; align: "left" | "right" }) {
  return (
    <div className={align === "left" ? "text-left" : "text-right"}>
      <div className="text-sm font-bold tracking-wide text-muted-foreground uppercase">{team.city}</div>
      <div className="font-display text-5xl leading-none font-bold tracking-wide uppercase max-md:text-3xl">
        {team.nickname}
      </div>
      {score !== null && (
        <div className="mt-3 font-display text-7xl leading-none font-bold tabular-nums max-md:text-5xl">{score}</div>
      )}
    </div>
  )
}

// what sits between the two teams: the clock, the result, or when it starts
function Centre({ game }: { game: Game }) {
  switch (game.status) {
    case "live":
      return (
        <>
          <div className="font-display text-3xl font-bold tracking-wide uppercase">
            {formatPeriod(game.period) || game.status_text}
          </div>
          {game.game_clock && <div className="text-xl tabular-nums">{game.game_clock}</div>}
        </>
      )
    case "final":
      return <div className="font-display text-3xl font-bold tracking-wide uppercase">{game.status_text || "Final"}</div>
    case "postponed":
      return <div className="font-display text-3xl font-bold tracking-wide text-destructive uppercase">Postponed</div>
    case "scheduled":
      return game.picks_open ? (
        <>
          <div className="text-xs font-bold tracking-wide text-muted-foreground uppercase">Tips off in</div>
          <div className="text-xl font-bold">
            <Countdown game={game} />
          </div>
        </>
      ) : (
        <div className="font-display text-3xl font-bold tracking-wide uppercase">Starting</div>
      )
  }
}

export function GameHeader({ game }: { game: Game }) {
  return (
    <section className="rounded-md border border-border bg-card p-8 max-md:p-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <StatusBadge game={game} />
        <span className="text-sm text-muted-foreground">{formatDateTime(game.tipoff_utc)}</span>
        {game.arena_name && (
          <span className="flex items-center gap-1 text-sm text-muted-foreground">
            <MapPin className="size-3.5" />
            {game.arena_name}
          </span>
        )}
      </div>

      <div className="mt-8 grid grid-cols-[1fr_auto_1fr] items-center gap-6 max-md:gap-3">
        <TeamBlock team={game.away_team} score={game.away_score} align="left" />
        <div className="text-center">
          <Centre game={game} />
        </div>
        <TeamBlock team={game.home_team} score={game.home_score} align="right" />
      </div>

      {game.status === "postponed" && (
        <p className="mt-6 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          This game has been postponed. Picks you've made are kept, and it reopens when the NBA sets a new date.
        </p>
      )}
    </section>
  )
}
