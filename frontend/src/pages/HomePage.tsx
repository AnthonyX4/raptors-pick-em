import { MediaCard } from "@/components/MediaCard"

// a stand-in until 16.3 puts the next game here: it shows the card style and links to the real routes
export function HomePage() {
  return (
    <section>
      <h1 className="text-3xl font-semibold tracking-tight">Pick'em</h1>
      <p className="mt-2 text-muted-foreground">Predict every Raptors game before tipoff and chat with other fans.</p>
      <div className="mt-10 grid grid-cols-3 gap-6 max-lg:grid-cols-2 max-md:grid-cols-1">
        <MediaCard to="/games" title="Make your picks" cta="See games" />
        <MediaCard to="/leaderboard" title="Leaderboard" cta="View standings" />
        <MediaCard to="/register" title="Join the game" cta="Sign up" />
      </div>
    </section>
  )
}
