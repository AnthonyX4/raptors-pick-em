import { ChevronRight } from "lucide-react"
import { Link } from "react-router"
import { formatDate, formatScore, formatTime } from "@/lib/format"
import type { Game } from "../api"
import { StatusBadge } from "./StatusBadge"

// one row of the schedule. away @ home, the way the nba writes it
export function GameCard({ game }: { game: Game }) {
  const played = game.status === "live" || game.status === "final"

  return (
    <Link
      to={`/games/${game.game_id}`}
      className="group flex items-center gap-6 rounded-md border border-border bg-card px-5 py-4 transition-colors hover:border-white/40 focus-visible:border-white/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none max-md:gap-3 max-md:px-4"
    >
      <div className="w-28 shrink-0 text-sm max-md:w-20">
        <div className="font-bold">{formatDate(game.tipoff_utc)}</div>
        <div className="text-muted-foreground">{formatTime(game.tipoff_utc)}</div>
      </div>
      <div className="min-w-0 flex-1 font-display text-2xl leading-tight font-bold tracking-wide uppercase max-md:text-lg">
        <span className="max-md:hidden">{game.away_team.full_name}</span>
        <span className="md:hidden">{game.away_team.tricode}</span>
        <span className="px-2 text-muted-foreground">@</span>
        <span className="max-md:hidden">{game.home_team.full_name}</span>
        <span className="md:hidden">{game.home_team.tricode}</span>
      </div>
      {played && (
        <div className="font-display text-2xl font-bold tabular-nums">
          {formatScore(game.away_score, game.home_score)}
        </div>
      )}
      <StatusBadge game={game} className="max-md:hidden" />
      <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground transition-colors group-hover:text-white" />
    </Link>
  )
}
