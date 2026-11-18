import { describe, expect, it } from "vitest"
import { avatarProblem, emailFormSchema, passwordFormSchema, usernameFormSchema } from "./schemas"

describe("settings forms", () => {
  it("takes a username the backend accepts", () => {
    expect(usernameFormSchema.safeParse({ username: "butter_69-x" }).success).toBe(true)
    expect(usernameFormSchema.safeParse({ username: "has space" }).success).toBe(false)
    expect(usernameFormSchema.safeParse({ username: "" }).success).toBe(false)
  })

  it("needs the current password to change the email", () => {
    expect(emailFormSchema.safeParse({ email: "a@b.co", currentPassword: "x" }).success).toBe(true)
    expect(emailFormSchema.safeParse({ email: "a@b.co", currentPassword: "" }).success).toBe(false)
    expect(emailFormSchema.safeParse({ email: "nope", currentPassword: "x" }).success).toBe(false)
  })

  it("wants a new password of at least 8 characters", () => {
    expect(passwordFormSchema.safeParse({ currentPassword: "old", newPassword: "12345678" }).success).toBe(true)
    expect(passwordFormSchema.safeParse({ currentPassword: "old", newPassword: "1234567" }).success).toBe(false)
  })
})

describe("avatarProblem", () => {
  const mb = 1024 * 1024

  it("accepts an image up to 5 MB", () => {
    expect(avatarProblem({ type: "image/png", size: 5 * mb })).toBeNull()
  })

  it("refuses a bigger one", () => {
    expect(avatarProblem({ type: "image/jpeg", size: 5 * mb + 1 })).toMatch(/over 5 MB/)
  })

  it("refuses something that isn't an image", () => {
    expect(avatarProblem({ type: "application/pdf", size: 100 })).toMatch(/image/)
  })
})
