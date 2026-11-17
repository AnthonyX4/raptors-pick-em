import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { useNow } from "@/hooks/useNow"
import { formatCountdown } from "@/lib/format"
import type { Game } from "../api"
import { allGamesKey, gameKey } from "../keys"

// counts down to tipoff. when it reaches zero the game is asked for once, so picks_open and the
// status come from the server rather than from this clock
export function Countdown({ game }: { game: Game }) {
  const queryClient = useQueryClient()
  const remaining = new Date(game.tipoff_utc).getTime() - useNow(1000)
  const elapsed = remaining <= 0
  const gameId = game.game_id

  useEffect(() => {
    if (!elapsed) return
    void queryClient.invalidateQueries({ queryKey: allGamesKey })
    void queryClient.invalidateQueries({ queryKey: gameKey(gameId) })
  }, [elapsed, gameId, queryClient])

  return <span className="tabular-nums">{elapsed ? "Starting…" : formatCountdown(remaining)}</span>
}
