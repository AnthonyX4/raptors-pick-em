import { cn } from "@/lib/utils"
import type { Game } from "../api"

// "starting" is a scheduled game whose tipoff has passed before the poller has marked it live
function label(game: Game) {
  switch (game.status) {
    case "live":
      return "Live"
    case "final":
      return "Final"
    case "postponed":
      return "Postponed"
    case "scheduled":
      return game.picks_open ? "Upcoming" : "Starting"
  }
}

export function StatusBadge({ game, className }: { game: Game; className?: string }) {
  const live = game.status === "live"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-xs font-bold tracking-wide uppercase",
        live && "border-primary bg-primary text-primary-foreground",
        game.status === "postponed" && "border-destructive/40 text-destructive",
        !live && game.status !== "postponed" && "border-border text-muted-foreground",
        className,
      )}
    >
      {live && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-white" />}
      {label(game)}
    </span>
  )
}
