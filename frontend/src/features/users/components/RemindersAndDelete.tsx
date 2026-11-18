import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import type { UserPrivate } from "@/features/auth/api"
import { errorMessage } from "@/features/auth/errors"
import type { useAccount } from "../hooks"
import { SettingsSection } from "./SettingsSection"

type Account = ReturnType<typeof useAccount>

// saved the moment it's flipped: it's a setting, not a credential, so no password is asked
export function RemindersToggle({ user, account }: { user: UserPrivate; account: Account }) {
  async function onChange(checked: boolean) {
    try {
      await account.update.mutateAsync({ email_reminders: checked })
    } catch (error) {
      toast.error(errorMessage(error))
    }
  }

  return (
    <SettingsSection title="Reminders">
      <div className="flex items-center justify-between gap-6">
        <Label htmlFor="email-reminders" className="flex-col items-start gap-1">
          <span className="text-base">Email me before tipoff</span>
          <span className="text-sm font-normal text-muted-foreground">
            A reminder a couple of hours before a game, if you haven't made all your picks.
          </span>
        </Label>
        <Switch
          id="email-reminders"
          checked={user.email_reminders}
          disabled={account.update.isPending}
          onCheckedChange={(checked) => void onChange(checked)}
        />
      </div>
    </SettingsSection>
  )
}

export function DeleteAccount({ account }: { account: Account }) {
  const [confirming, setConfirming] = useState(false)

  async function onConfirm() {
    try {
      await account.deleteAccount.mutateAsync() // logs out on success
      toast.success("Your account was deleted")
    } catch (error) {
      setConfirming(false)
      toast.error(errorMessage(error))
    }
  }

  return (
    <SettingsSection
      title="Delete account"
      description="Removes your account, your picks and your likes. Your chat messages stay, shown as [deleted]. This can't be undone."
      danger
    >
      <Button variant="destructive" onClick={() => setConfirming(true)}>
        Delete my account
      </Button>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete your account?"
        description="Your picks and likes are removed for good, and your messages are left as [deleted]."
        confirmLabel="Delete my account"
        pending={account.deleteAccount.isPending}
        onConfirm={() => void onConfirm()}
      />
    </SettingsSection>
  )
}
