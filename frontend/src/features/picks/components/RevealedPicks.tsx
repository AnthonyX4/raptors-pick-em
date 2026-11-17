import { useMemo } from "react"
import { Link } from "react-router"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/features/auth/useAuth"
import type { GameDetail } from "@/features/games/api"
import { cn } from "@/lib/utils"
import { answerText, pointsText, totalPoints } from "../answer"
import type { PickWithUser } from "../api"
import { useGamePicks } from "../hooks"

// the api orders by user, so a user's picks are together unless they straddle two pages: grouping by id
// across all the loaded pages puts them back together either way
function groupByUser(picks: PickWithUser[]) {
  const groups = new Map<number, { user: PickWithUser["user"]; picks: PickWithUser[] }>()
  for (const pick of picks) {
    const group = groups.get(pick.user.user_id)
    if (group) group.picks.push(pick)
    else groups.set(pick.user.user_id, { user: pick.user, picks: [pick] })
  }
  return [...groups.values()]
}

// everyone's picks. only mounted for a game that has started, because before that the api says 403
export function RevealedPicks({ game }: { game: GameDetail }) {
  const { user: me } = useAuth()
  const query = useGamePicks(game.game_id, game.status)
  const groups = useMemo(
    () => groupByUser(query.data?.pages.flatMap((page) => page.picks) ?? []),
    [query.data],
  )

  let body: React.ReactNode
  if (query.isPending) {
    body = <Skeleton className="h-32 w-full" />
  } else if (query.isError) {
    body = <p className="text-sm text-muted-foreground">Couldn't load everyone's picks. Try refreshing the page.</p>
  } else if (groups.length === 0) {
    body = <p className="text-muted-foreground">Nobody made a pick for this game.</p>
  } else {
    body = (
      <>
        <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1">
          {groups.map(({ user, picks }) => {
            const total = totalPoints(picks)
            return (
              <div
                key={user.user_id}
                className={cn(
                  "rounded-md border bg-card p-5",
                  user.user_id === me?.user_id ? "border-primary" : "border-border",
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <Link to={`/users/${user.user_id}`} className="flex min-w-0 items-center gap-3 hover:underline">
                    <Avatar className="size-8">
                      <AvatarImage src={user.image_path} alt="" />
                      <AvatarFallback>{user.username.slice(0, 1).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <span className="truncate font-bold">{user.username}</span>
                  </Link>
                  {total !== null && <span className="font-display text-xl font-bold">{pointsText(total)}</span>}
                </div>
                <dl className="mt-4 space-y-2 text-sm">
                  {picks.map((pick) => (
                    <div key={pick.pick_id} className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">{pick.category.name}</dt>
                      <dd className="text-right">
                        {answerText(pick)}
                        {pick.points_awarded !== null && (
                          <span className={cn("ml-2", pick.points_awarded > 0 ? "font-bold" : "text-muted-foreground")}>
                            {pick.points_awarded > 0 ? `+${pick.points_awarded}` : "0"}
                          </span>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )
          })}
        </div>
        {query.hasNextPage && (
          <Button
            variant="outline"
            className="mt-6 font-bold tracking-wide uppercase"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? "Loading…" : "Show more"}
          </Button>
        )}
      </>
    )
  }

  return (
    <section>
      <h2 className="mb-4 font-display text-3xl font-bold tracking-wide uppercase">Everyone's picks</h2>
      {body}
    </section>
  )
}
