import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Link } from "react-router"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { forgotPassword } from "@/features/auth/api"
import { AuthCard, FormError } from "@/features/auth/components/AuthCard"
import { errorMessage } from "@/features/auth/errors"
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/features/auth/schemas"

export function ForgotPasswordPage() {
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema), defaultValues: { email: "" } })

  async function onSubmit(values: ForgotPasswordValues) {
    setServerError(null)
    try {
      await forgotPassword(values.email)
      setSentTo(values.email)
    } catch (error) {
      setServerError(errorMessage(error))
    }
  }

  const back = (
    <p>
      <Link to="/login" className="underline underline-offset-4 hover:text-foreground">
        Back to log in
      </Link>
    </p>
  )

  // the backend answers 202 whether or not the address has an account, and so does this page
  if (sentTo) {
    return (
      <AuthCard title="Check your email" footer={back}>
        <p role="status" className="text-sm">
          If <span className="font-semibold">{sentTo}</span> has an account, we've sent a link to reset the password. It can
          take a minute to arrive.
        </p>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title="Forgot password"
      description="Enter your email and we'll send you a link to choose a new password."
      footer={back}
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormError message={serverError} />
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input type="email" autoComplete="email" autoFocus {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className="w-full font-bold uppercase tracking-wide" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      </Form>
    </AuthCard>
  )
}
