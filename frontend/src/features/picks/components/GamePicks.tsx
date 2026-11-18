import { Link, useLocation } from "react-router"
import { Button } from "@/components/ui/button"
import { ErrorState, Loading } from "@/components/states"
import { useAuth } from "@/features/auth/useAuth"
import type { GameDetail } from "@/features/games/api"
import { useCategories, useMyPicks, useRoster } from "../hooks"
import { MyPicks } from "./MyPicks"
import { PickForm } from "./PickForm"
import { RevealedPicks } from "./RevealedPicks"

const heading = "mb-4 font-display text-3xl font-bold tracking-wide uppercase"

function LoginPrompt() {
  const location = useLocation()
  return (
    <section>
      <h2 className={heading}>Make your picks</h2>
      <div className="rounded-md border border-border bg-card p-8 max-md:p-5">
        <p className="text-muted-foreground">Log in to pick the winner, the margin and the Raptors' stat leaders.</p>
        <div className="mt-6 flex gap-3">
          {/* login sends people back to where they were */}
          <Button asChild className="font-bold tracking-wide uppercase">
            <Link to="/login" state={{ from: location }}>Log in</Link>
          </Button>
          <Button asChild variant="outline" className="font-bold tracking-wide uppercase">
            <Link to="/register" state={{ from: location }}>Sign up</Link>
          </Button>
        </div>
      </div>
    </section>
  )
}

// the form needs the categories, the roster and the person's saved picks before it can be seeded
function PickEditor({ game }: { game: GameDetail }) {
  const categories = useCategories()
  const roster = useRoster()
  const saved = useMyPicks(game.game_id, game.status)

  let body: React.ReactNode
  if (categories.isPending || roster.isPending || saved.isPending) {
    body = <Loading what="the pick form" className="h-72 w-full" />
  } else if (categories.isError || roster.isError || saved.isError) {
    // ask again for whatever failed; the ones that loaded are cached and answer at once
    const retry = () => {
      for (const query of [categories, roster, saved]) if (query.isError) void query.refetch()
    }
    body = (
      <ErrorState
        what="the pick form"
        onRetry={retry}
        retrying={categories.isFetching || roster.isFetching || saved.isFetching}
      />
    )
  } else {
    body = <PickForm game={game} categories={categories.data} roster={roster.data} saved={saved.data} />
  }

  return (
    <section>
      <h2 className={heading}>Your picks</h2>
      {body}
    </section>
  )
}

// what picks look like for this game, from the api's own flags rather than the clock:
// picks_open is the form, anything else is read-only, and the reveal is for games that have started
export function GamePicks({ game }: { game: GameDetail }) {
  const { user, isLoading } = useAuth()

  if (isLoading) return <Loading what="your picks" className="h-48 w-full" />
  if (game.picks_open) return user ? <PickEditor game={game} /> : <LoginPrompt />

  // a postponed game is closed but never played: its picks stay hidden until it is
  const revealed = game.status !== "postponed"
  return (
    <div className="space-y-10">
      {user && <MyPicks game={game} />}
      {revealed && <RevealedPicks game={game} />}
    </div>
  )
}
