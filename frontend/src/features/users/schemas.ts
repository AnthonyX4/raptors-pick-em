import { z } from "zod"
import { emailSchema, passwordSchema, usernameSchema } from "@/features/auth/schemas"
import { AVATAR_MAX_BYTES } from "@/lib/constants"

// the settings forms reuse the auth rules, which mirror the backend's; the server stays the authority
export const usernameFormSchema = z.object({ username: usernameSchema })

// changing the email needs the current password, so a stolen token alone can't take the account
export const emailFormSchema = z.object({
  email: emailSchema,
  currentPassword: z.string().min(1, "Enter your current password"),
})

export const passwordFormSchema = z.object({
  currentPassword: z.string().min(1, "Enter your current password"),
  newPassword: passwordSchema,
})

export type UsernameFormValues = z.infer<typeof usernameFormSchema>
export type EmailFormValues = z.infer<typeof emailFormSchema>
export type PasswordFormValues = z.infer<typeof passwordFormSchema>

// a reason not to upload this file, or null. the api checks the size and decodes the image itself
export function avatarProblem(file: { size: number; type: string }): string | null {
  if (!file.type.startsWith("image/")) return "Choose an image file (JPEG, PNG, GIF or WebP)."
  if (file.size > AVATAR_MAX_BYTES) return `That picture is over ${AVATAR_MAX_BYTES / (1024 * 1024)} MB.`
  return null
}
