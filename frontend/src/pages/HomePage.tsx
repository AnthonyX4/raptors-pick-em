import { MediaCard } from "@/components/MediaCard"
import { NextGame } from "@/features/games/components/NextGame"
import { useAuth } from "@/features/auth/useAuth"

export function HomePage() {
  const { user, isLoading } = useAuth()

  return (
    <section className="mx-auto max-w-6xl">
      <h1 className="font-display text-5xl leading-none font-bold tracking-wide uppercase">Pick'em</h1>
      <p className="mt-3 text-muted-foreground">Predict every Raptors game before tipoff and chat with other fans.</p>
      <div className="mt-8">
        <NextGame />
      </div>
      <div className="mt-10 grid grid-cols-3 gap-6 max-lg:grid-cols-2 max-md:grid-cols-1">
        <MediaCard to="/games" title="The schedule" cta="See games" />
        <MediaCard to="/leaderboard" title="Leaderboard" cta="View standings" />
        {/* not while a stored token is still being checked, or a logged-in person sees it flash */}
        {!isLoading && !user && <MediaCard to="/register" title="Join the game" cta="Sign up" />}
      </div>
    </section>
  )
}
