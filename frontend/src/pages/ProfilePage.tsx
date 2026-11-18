import { Link, useParams } from "react-router"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/features/auth/useAuth"
import { useUser } from "@/features/users/hooks"
import { ApiError } from "@/lib/api-client"

// the api shows another user's name and picture and nothing else, so that is all a profile is
export function ProfilePage() {
  const userId = Number(useParams().userId)
  const { user: me } = useAuth()
  const { data: user, isPending, error } = useUser(userId)

  if (isPending && Number.isInteger(userId)) {
    return (
      <div className="mx-auto flex max-w-2xl items-center gap-6">
        <Skeleton className="size-28 rounded-full" />
        <Skeleton className="h-12 w-64" />
      </div>
    )
  }

  if (error || !user) {
    // a bad id in the url is as good as a missing user
    const notFound = !Number.isInteger(userId) || (error instanceof ApiError && error.status === 404)
    return (
      <section className="mx-auto max-w-2xl">
        <h1 className="font-display text-4xl leading-none font-bold tracking-wide uppercase">
          {notFound ? "User not found" : "Couldn't load this profile"}
        </h1>
        <p className="mt-3 text-muted-foreground">
          {notFound ? "There's no one with that id." : "Try refreshing the page."}{" "}
          <Link to="/leaderboard" className="text-white underline underline-offset-4">
            Back to the leaderboard
          </Link>
        </p>
      </section>
    )
  }

  const isMe = me?.user_id === user.user_id
  return (
    <section className="mx-auto flex max-w-2xl items-center gap-8 max-md:flex-col max-md:items-start max-md:gap-5">
      <Avatar className="size-28">
        <AvatarImage src={user.image_path} alt={`${user.username}'s profile picture`} />
        <AvatarFallback className="text-4xl">{user.username.slice(0, 1).toUpperCase()}</AvatarFallback>
      </Avatar>
      <div className="min-w-0">
        <h1 className="font-display text-5xl leading-none font-bold tracking-wide break-words uppercase">{user.username}</h1>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button asChild variant="outline" className="font-bold tracking-wide uppercase">
            <Link to="/leaderboard">Leaderboard</Link>
          </Button>
          {isMe && (
            <Button asChild className="font-bold tracking-wide uppercase">
              <Link to="/settings">Edit profile</Link>
            </Button>
          )}
        </div>
      </div>
    </section>
  )
}
