import { describe, expect, it } from "vitest"
import { muteSchema } from "./schemas"

const check = (hours: string, reason = "") => muteSchema.safeParse({ hours, reason }).success

describe("muteSchema", () => {
  it("takes 1 to 720 whole hours", () => {
    expect(check("1")).toBe(true)
    expect(check("24")).toBe(true)
    expect(check("720")).toBe(true)
  })

  it("refuses anything else", () => {
    for (const bad of ["", "0", "721", "-1", "1.5", "abc"]) expect(check(bad)).toBe(false)
  })

  it("keeps the reason to 200 characters", () => {
    expect(check("1", "x".repeat(200))).toBe(true)
    expect(check("1", "x".repeat(201))).toBe(false)
  })
})
