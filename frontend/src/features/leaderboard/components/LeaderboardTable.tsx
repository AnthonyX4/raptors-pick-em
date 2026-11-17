import { Link } from "react-router"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useAuth } from "@/features/auth/useAuth"
import { cn } from "@/lib/utils"
import type { LeaderboardEntry } from "../api"

interface LeaderboardTableProps {
  entries: LeaderboardEntry[]
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
  showGames?: boolean // a single game's board has no use for "games played"
}

// standings, with the logged-in person's row marked. ranks are the api's: tied totals share one
export function LeaderboardTable({ entries, hasMore, loadingMore, onLoadMore, showGames = true }: LeaderboardTableProps) {
  const { user: me } = useAuth()

  return (
    <>
      <div className="rounded-md border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead>Player</TableHead>
              <TableHead className="text-right">Points</TableHead>
              <TableHead className="text-right">Correct</TableHead>
              {showGames && <TableHead className="text-right max-md:hidden">Games</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => {
              const mine = entry.user.user_id === me?.user_id
              return (
                <TableRow key={entry.user.user_id} className={cn("tabular-nums", mine && "bg-primary/10")} data-mine={mine || undefined}>
                  <TableCell className="font-display text-xl font-bold">{entry.rank}</TableCell>
                  <TableCell>
                    <Link to={`/users/${entry.user.user_id}`} className="flex items-center gap-3 hover:underline">
                      <Avatar className="size-7">
                        <AvatarImage src={entry.user.image_path} alt="" />
                        <AvatarFallback>{entry.user.username.slice(0, 1).toUpperCase()}</AvatarFallback>
                      </Avatar>
                      <span className="truncate font-medium">{entry.user.username}</span>
                      {mine && <span className="text-xs font-bold tracking-wide text-primary uppercase">You</span>}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right font-display text-xl font-bold">{entry.total_points}</TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {entry.correct_picks}/{entry.picks_scored}
                  </TableCell>
                  {showGames && (
                    <TableCell className="text-right text-muted-foreground max-md:hidden">{entry.games_played}</TableCell>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
      {hasMore && (
        <Button
          variant="outline"
          className="mt-6 font-bold tracking-wide uppercase"
          onClick={onLoadMore}
          disabled={loadingMore}
        >
          {loadingMore ? "Loading…" : "Show more"}
        </Button>
      )}
    </>
  )
}
