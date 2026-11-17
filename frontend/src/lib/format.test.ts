import { describe, expect, it } from "vitest"
import { formatCountdown, formatPeriod, formatScore } from "@/lib/format"

describe("formatPeriod", () => {
  it("labels quarters and overtimes", () => {
    expect(formatPeriod(1)).toBe("Q1")
    expect(formatPeriod(4)).toBe("Q4")
    expect(formatPeriod(5)).toBe("OT")
    expect(formatPeriod(6)).toBe("2OT")
  })

  it("is empty when there's no period yet", () => {
    expect(formatPeriod(null)).toBe("")
    expect(formatPeriod(undefined)).toBe("")
  })
})

describe("formatCountdown", () => {
  const minute = 60_000
  const hour = 60 * minute
  const day = 24 * hour

  it("drops the units that are too small to matter", () => {
    expect(formatCountdown(2 * day + 3 * hour + 14 * minute + 59_000)).toBe("2d 3h 14m")
    expect(formatCountdown(3 * hour + 14 * minute + 5_000)).toBe("3h 14m 05s")
    expect(formatCountdown(14 * minute + 5_000)).toBe("14m 05s")
  })

  it("never goes negative", () => {
    expect(formatCountdown(-5_000)).toBe("0m 00s")
  })
})

describe("formatScore", () => {
  it("shows a dash until there is a score", () => {
    expect(formatScore(null, null)).toBe("–")
    expect(formatScore(104, 99)).toBe("104–99")
  })
})
