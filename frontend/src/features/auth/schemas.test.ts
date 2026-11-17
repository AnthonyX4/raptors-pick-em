import { describe, expect, it } from "vitest"
import { loginSchema, registerSchema, resetPasswordSchema } from "./schemas"

const valid = { username: "raptors_fan-1", email: "fan@example.com", password: "longenough" }

// these mirror the backend's rules (schemas.py); if the backend changes them, change both
describe("registerSchema", () => {
  it("accepts a good account", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true)
  })

  it.each(["has space", "at@sign", "dot.name", "ünïcode", ""])("rejects the username %j", (username) => {
    expect(registerSchema.safeParse({ ...valid, username }).success).toBe(false)
  })

  it("allows 50 characters of username but not 51", () => {
    expect(registerSchema.safeParse({ ...valid, username: "a".repeat(50) }).success).toBe(true)
    expect(registerSchema.safeParse({ ...valid, username: "a".repeat(51) }).success).toBe(false)
  })

  it("wants a real email", () => {
    expect(registerSchema.safeParse({ ...valid, email: "not-an-email" }).success).toBe(false)
  })

  it("wants at least 8 characters of password", () => {
    expect(registerSchema.safeParse({ ...valid, password: "1234567" }).success).toBe(false)
    expect(registerSchema.safeParse({ ...valid, password: "12345678" }).success).toBe(true)
  })

  it("explains each failure in words", () => {
    const result = registerSchema.safeParse({ username: "bad name", email: "x", password: "short" })
    const messages = result.error?.issues.map((issue) => issue.message)
    expect(messages).toEqual(["Letters, digits, _ and - only", "Enter a valid email address", "At least 8 characters"])
  })
})

describe("loginSchema", () => {
  it("doesn't apply the 8 character rule, so old short passwords can still log in", () => {
    expect(loginSchema.safeParse({ email: "fan@example.com", password: "abc" }).success).toBe(true)
  })

  it("still needs a password", () => {
    expect(loginSchema.safeParse({ email: "fan@example.com", password: "" }).success).toBe(false)
  })
})

describe("resetPasswordSchema", () => {
  it("wants at least 8 characters", () => {
    expect(resetPasswordSchema.safeParse({ newPassword: "short" }).success).toBe(false)
    expect(resetPasswordSchema.safeParse({ newPassword: "long enough" }).success).toBe(true)
  })
})
