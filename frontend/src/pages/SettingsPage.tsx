import { Link } from "react-router"
import { useAuth } from "@/features/auth/useAuth"
import { EmailForm, PasswordForm, UsernameForm } from "@/features/users/components/AccountForms"
import { AvatarSection } from "@/features/users/components/AvatarSection"
import { DeleteAccount, RemindersToggle } from "@/features/users/components/RemindersAndDelete"
import { useAccount } from "@/features/users/hooks"

// only reached through ProtectedRoute, which waits for the user to load
export function SettingsPage() {
  const { user } = useAuth()
  if (!user) return null
  return <Settings user={user} />
}

function Settings({ user }: { user: NonNullable<ReturnType<typeof useAuth>["user"]> }) {
  const account = useAccount(user)

  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="font-display text-5xl leading-none font-bold tracking-wide uppercase">Settings</h1>
      <p className="mt-3 text-muted-foreground">
        <Link to={`/users/${user.user_id}`} className="underline underline-offset-4 hover:text-foreground">
          View your profile
        </Link>
      </p>
      <div className="mt-8 space-y-6">
        <AvatarSection user={user} account={account} />
        <UsernameForm user={user} account={account} />
        <EmailForm user={user} account={account} />
        <PasswordForm account={account} />
        <RemindersToggle user={user} account={account} />
        <DeleteAccount account={account} />
      </div>
    </section>
  )
}
