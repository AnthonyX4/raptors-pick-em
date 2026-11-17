import { describe, expect, it } from "vitest"
import { currentSeason } from "./season"

const game = (season: string, status: "final" | "scheduled" | "live" | "postponed") => ({ season, status })

describe("currentSeason", () => {
  it("is the season of the first game still to play", () => {
    expect(currentSeason([game("2025-26", "final"), game("2026-27", "final"), game("2026-27", "scheduled")])).toBe("2026-27")
  })

  it("counts a live game as the one being played", () => {
    expect(currentSeason([game("2026-27", "final"), game("2026-27", "live")])).toBe("2026-27")
  })

  it("is the last game's season once everything is final", () => {
    expect(currentSeason([game("2025-26", "final"), game("2026-27", "final")])).toBe("2026-27")
  })

  it("is null with no games", () => {
    expect(currentSeason([])).toBeNull()
  })
})
