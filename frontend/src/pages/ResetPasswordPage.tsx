import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Link, useNavigate, useSearchParams } from "react-router"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { ApiError } from "@/lib/api-client"
import { resetPassword } from "@/features/auth/api"
import { AuthCard, FormError } from "@/features/auth/components/AuthCard"
import { errorMessage } from "@/features/auth/errors"
import { resetPasswordSchema, type ResetPasswordValues } from "@/features/auth/schemas"

const requestNewLink = (
  <p>
    <Link to="/forgot-password" className="underline underline-offset-4 hover:text-foreground">
      Request a new link
    </Link>
  </p>
)

// the emailed link lands here as /reset-password?token=...
export function ResetPasswordPage() {
  const token = useSearchParams()[0].get("token")
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [tokenRejected, setTokenRejected] = useState(false)
  const form = useForm<ResetPasswordValues>({ resolver: zodResolver(resetPasswordSchema), defaultValues: { newPassword: "" } })

  if (!token) {
    return (
      <AuthCard title="Reset password" footer={requestNewLink}>
        <p className="text-sm">This link is missing its token. Open the link from the email again, or ask for a new one.</p>
      </AuthCard>
    )
  }

  async function onSubmit(values: ResetPasswordValues) {
    setServerError(null)
    try {
      await resetPassword(token!, values.newPassword)
      toast.success("Password changed. Log in with your new password.")
      navigate("/login", { replace: true })
    } catch (error) {
      // a 400 means the token is used, expired or wrong: only a new email helps, so say so
      setTokenRejected(error instanceof ApiError && error.status === 400)
      setServerError(errorMessage(error))
    }
  }

  return (
    <AuthCard
      title="Reset password"
      description="Choose a new password for your account."
      footer={tokenRejected ? requestNewLink : undefined}
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormError message={serverError} />
          <FormField
            control={form.control}
            name="newPassword"
            render={({ field }) => (
              <FormItem>
                <FormLabel>New password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" autoFocus {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className="w-full font-bold uppercase tracking-wide" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : "Change password"}
          </Button>
        </form>
      </Form>
    </AuthCard>
  )
}
