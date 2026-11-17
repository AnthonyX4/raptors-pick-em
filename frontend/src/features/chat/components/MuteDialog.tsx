import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { FormError } from "@/features/auth/components/AuthCard"
import type { ChatUser } from "../api"
import { chatErrorMessage } from "../errors"
import type { ChatActions } from "../hooks"
import { muteSchema, type MuteValues } from "../schemas"

interface MuteDialogProps {
  user: ChatUser
  open: boolean
  onOpenChange: (open: boolean) => void
  mute: ChatActions["mute"]
}

// an admin silences someone for a while. the server refuses to mute another admin, and says so here
export function MuteDialog({ user, open, onOpenChange, mute }: MuteDialogProps) {
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<MuteValues>({ resolver: zodResolver(muteSchema), defaultValues: { hours: "24", reason: "" } })

  async function onSubmit(values: MuteValues) {
    setServerError(null)
    const hours = Number(values.hours)
    try {
      await mute.mutateAsync({ userId: user.user_id, hours, reason: values.reason.trim() || null })
      toast.success(`${user.username} is muted for ${hours} ${hours === 1 ? "hour" : "hours"}`)
      onOpenChange(false)
    } catch (error) {
      setServerError(chatErrorMessage(error))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mute {user.username}</DialogTitle>
          <DialogDescription>They can still read the chat, but can't post, edit or like until it ends.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <FormError message={serverError} />
            <FormField
              control={form.control}
              name="hours"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Hours</FormLabel>
                  <FormControl>
                    <Input type="number" inputMode="numeric" min={1} max={720} className="max-w-32" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason (optional)</FormLabel>
                  <FormControl>
                    <Input maxLength={200} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="destructive" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? "Muting…" : "Mute"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
