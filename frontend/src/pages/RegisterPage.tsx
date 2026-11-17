import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Link, Navigate } from "react-router"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { ApiError } from "@/lib/api-client"
import { AuthCard, FormError } from "@/features/auth/components/AuthCard"
import { errorMessage } from "@/features/auth/errors"
import { registerSchema, type RegisterValues } from "@/features/auth/schemas"
import { useAuth } from "@/features/auth/useAuth"
import { useReturnTo } from "@/features/auth/useReturnTo"

export function RegisterPage() {
  const { user, register } = useAuth()
  const returnTo = useReturnTo()
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { username: "", email: "", password: "" },
  })

  if (user) return <Navigate to={returnTo} replace />

  async function onSubmit(values: RegisterValues) {
    setServerError(null)
    try {
      await register(values) // creates the account, then logs in
    } catch (error) {
      // the backend answers 409 "Username already exists" or "User already exists" (the email): put it on the field
      if (error instanceof ApiError && error.status === 409) {
        const usernameTaken = error.message.startsWith("Username")
        form.setError(usernameTaken ? "username" : "email", {
          message: usernameTaken ? "That username is taken" : "An account with that email already exists",
        })
      } else {
        setServerError(errorMessage(error))
      }
    }
  }

  return (
    <AuthCard
      title="Sign up"
      description="Predict every Raptors game and chat with other fans."
      footer={
        <p>
          Already have an account?{" "}
          <Link
            to="/login"
            state={returnTo === "/" ? undefined : { from: { pathname: returnTo } }}
            className="underline underline-offset-4 hover:text-foreground"
          >
            Log in
          </Link>
        </p>
      }
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormError message={serverError} />
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Username</FormLabel>
                <FormControl>
                  <Input autoComplete="username" autoFocus {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
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
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className="w-full font-bold uppercase tracking-wide" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Creating account…" : "Create account"}
          </Button>
        </form>
      </Form>
    </AuthCard>
  )
}
