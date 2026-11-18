import { useRef } from "react"
import { toast } from "sonner"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import type { UserPrivate } from "@/features/auth/api"
import { errorMessage } from "@/features/auth/errors"
import type { useAccount } from "../hooks"
import { avatarProblem } from "../schemas"
import { SettingsSection } from "./SettingsSection"

export function AvatarSection({ user, account }: { user: UserPrivate; account: ReturnType<typeof useAccount> }) {
  const input = useRef<HTMLInputElement>(null)
  const busy = account.uploadPicture.isPending || account.removePicture.isPending

  async function onFile(file: File | undefined) {
    if (input.current) input.current.value = "" // so choosing the same file again still fires
    if (!file) return
    const problem = avatarProblem(file)
    if (problem) {
      toast.error(problem)
      return
    }
    try {
      await account.uploadPicture.mutateAsync(file)
      toast.success("Picture updated")
    } catch (error) {
      toast.error(errorMessage(error))
    }
  }

  async function onRemove() {
    try {
      await account.removePicture.mutateAsync()
      toast.success("Picture removed")
    } catch (error) {
      toast.error(errorMessage(error))
    }
  }

  return (
    <SettingsSection title="Profile picture" description="JPEG, PNG, GIF or WebP, up to 5 MB.">
      <div className="flex items-center gap-6">
        <Avatar className="size-20">
          <AvatarImage src={user.image_path} alt="Your profile picture" />
          <AvatarFallback className="text-2xl">{user.username.slice(0, 1).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div className="flex flex-wrap gap-3">
          <input
            ref={input}
            type="file"
            accept="image/*"
            className="sr-only"
            tabIndex={-1}
            aria-label="Choose a profile picture"
            onChange={(event) => void onFile(event.target.files?.[0])}
          />
          <Button type="button" variant="outline" disabled={busy} onClick={() => input.current?.click()}>
            {account.uploadPicture.isPending ? "Uploading…" : "Upload a picture"}
          </Button>
          {/* image_file is null while the default picture is showing: nothing to remove */}
          {user.image_file && (
            <Button type="button" variant="ghost" disabled={busy} onClick={() => void onRemove()}>
              Remove
            </Button>
          )}
        </div>
      </div>
    </SettingsSection>
  )
}
