import { describe, expect, it } from "vitest"
import { ApiError } from "@/lib/api-client"
import { chatErrorMessage } from "./errors"

describe("chatErrorMessage", () => {
  it("rewrites the mute time into the reader's own format", () => {
    const text = chatErrorMessage(new ApiError(403, "You're muted until 2026-11-17T21:30:00+00:00"))
    expect(text).toMatch(/^You're muted until /)
    expect(text).not.toContain("T21:30:00+00:00")
  })

  it("leaves other messages alone", () => {
    expect(chatErrorMessage(new ApiError(409, "This game's chat is closed"))).toBe("This game's chat is closed")
  })
})
