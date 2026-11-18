import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import type { UserPrivate } from "@/features/auth/api"
import { FormError } from "@/features/auth/components/AuthCard"
import { errorMessage } from "@/features/auth/errors"
import type { useAccount } from "../hooks"
import {
  emailFormSchema,
  passwordFormSchema,
  usernameFormSchema,
  type EmailFormValues,
  type PasswordFormValues,
  type UsernameFormValues,
} from "../schemas"
import { SettingsSection } from "./SettingsSection"

type Account = ReturnType<typeof useAccount>
const submitClass = "font-bold tracking-wide uppercase"

export function UsernameForm({ user, account }: { user: UserPrivate; account: Account }) {
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<UsernameFormValues>({
    resolver: zodResolver(usernameFormSchema),
    defaultValues: { username: user.username },
  })

  async function onSubmit(values: UsernameFormValues) {
    setServerError(null)
    try {
      const updated = await account.update.mutateAsync({ username: values.username })
      form.reset({ username: updated.username })
      toast.success("Username changed")
    } catch (error) {
      setServerError(errorMessage(error)) // "Username already exists"
    }
  }

  return (
    <SettingsSection title="Username" description="Shown on your messages, picks and the leaderboard.">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="max-w-sm space-y-4" noValidate>
          <FormError message={serverError} />
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Username</FormLabel>
                <FormControl>
                  <Input autoComplete="username" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className={submitClass} disabled={!form.formState.isDirty || form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : "Save username"}
          </Button>
        </form>
      </Form>
    </SettingsSection>
  )
}

export function EmailForm({ user, account }: { user: UserPrivate; account: Account }) {
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<EmailFormValues>({
    resolver: zodResolver(emailFormSchema),
    defaultValues: { email: user.email, currentPassword: "" },
  })

  async function onSubmit(values: EmailFormValues) {
    setServerError(null)
    try {
      const updated = await account.update.mutateAsync({ email: values.email, current_password: values.currentPassword })
      form.reset({ email: updated.email, currentPassword: "" })
      toast.success("Email changed")
    } catch (error) {
      setServerError(errorMessage(error)) // wrong password, or "Email already in use"
    }
  }

  return (
    <SettingsSection title="Email" description="Where password resets and pick reminders go. Changing it needs your password.">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="max-w-sm space-y-4" noValidate>
          <FormError message={serverError} />
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input type="email" autoComplete="email" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="currentPassword"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Current password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="current-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className={submitClass} disabled={!form.formState.isDirty || form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : "Save email"}
          </Button>
        </form>
      </Form>
    </SettingsSection>
  )
}

export function PasswordForm({ account }: { account: Account }) {
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordFormSchema),
    defaultValues: { currentPassword: "", newPassword: "" },
  })

  async function onSubmit(values: PasswordFormValues) {
    setServerError(null)
    try {
      await account.changePassword.mutateAsync(values)
      form.reset()
      toast.success("Password changed")
    } catch (error) {
      setServerError(errorMessage(error)) // "Current password is incorrect"
    }
  }

  return (
    <SettingsSection title="Password">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="max-w-sm space-y-4" noValidate>
          <FormError message={serverError} />
          <FormField
            control={form.control}
            name="currentPassword"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Current password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="current-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="newPassword"
            render={({ field }) => (
              <FormItem>
                <FormLabel>New password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className={submitClass} disabled={!form.formState.isDirty || form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : "Change password"}
          </Button>
        </form>
      </Form>
    </SettingsSection>
  )
}
