import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Link, Navigate } from "react-router"
import { Button } from "@/components/ui/button"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { AuthCard, FormError } from "@/features/auth/components/AuthCard"
import { errorMessage } from "@/features/auth/errors"
import { loginSchema, type LoginValues } from "@/features/auth/schemas"
import { useAuth } from "@/features/auth/useAuth"
import { useReturnTo } from "@/features/auth/useReturnTo"

export function LoginPage() {
  const { user, login } = useAuth()
  const returnTo = useReturnTo()
  const [serverError, setServerError] = useState<string | null>(null)
  const form = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } })

  // logging in (or already being logged in) leaves this page for where the person was going
  if (user) return <Navigate to={returnTo} replace />

  async function onSubmit(values: LoginValues) {
    setServerError(null)
    try {
      await login(values.email, values.password)
    } catch (error) {
      setServerError(errorMessage(error))
    }
  }

  return (
    <AuthCard
      title="Log in"
      footer={
        <>
          <p>
            <Link to="/forgot-password" className="underline underline-offset-4 hover:text-foreground">
              Forgot your password?
            </Link>
          </p>
          <p>
            New here?{" "}
            <Link to="/register" state={carryDestination(returnTo)} className="underline underline-offset-4 hover:text-foreground">
              Create an account
            </Link>
          </p>
        </>
      }
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
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="current-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" className="w-full font-bold uppercase tracking-wide" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Logging in…" : "Log in"}
          </Button>
        </form>
      </Form>
    </AuthCard>
  )
}

// keeps the destination when someone switches from log in to register
function carryDestination(returnTo: string) {
  return returnTo === "/" ? undefined : { from: { pathname: returnTo } }
}
