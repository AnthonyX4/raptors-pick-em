import { z } from "zod"

// the same rules the backend enforces (schemas.py), so mistakes show before a round trip.
// the server stays the authority: a 422 or 409 still reaches the form as an error
export const usernameSchema = z
  .string()
  .min(1, "Choose a username")
  .max(50, "At most 50 characters")
  .regex(/^[A-Za-z0-9_-]+$/, "Letters, digits, _ and - only")

export const emailSchema = z.email({ error: "Enter a valid email address" })

export const passwordSchema = z.string().min(8, "At least 8 characters")

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password"), // not the 8 character rule: older passwords must still log in
})

export const registerSchema = z.object({
  username: usernameSchema,
  email: emailSchema,
  password: passwordSchema,
})

export const forgotPasswordSchema = z.object({ email: emailSchema })

export const resetPasswordSchema = z.object({ newPassword: passwordSchema })

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>
