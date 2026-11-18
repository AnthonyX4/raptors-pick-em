import { describe, expect, it } from "vitest"
import { parseChatEvent } from "./events"

describe("parseChatEvent", () => {
  it("reads each of the four event types", () => {
    const likes = parseChatEvent('{"type":"message.likes","message_id":5,"like_count":2}')
    expect(likes).toEqual({ type: "message.likes", message_id: 5, like_count: 2 })
    expect(parseChatEvent('{"type":"message.deleted","message_id":5}')?.type).toBe("message.deleted")
    expect(parseChatEvent('{"type":"message.edited","message_id":5,"body":"b","edited_at":"x"}')?.type).toBe(
      "message.edited",
    )
    expect(parseChatEvent('{"type":"message.created","message":{"message_id":5}}')?.type).toBe("message.created")
  })

  it("gives null for text that isn't JSON", () => {
    expect(parseChatEvent("not json")).toBeNull()
  })

  it("gives null for JSON that isn't an object with a type", () => {
    expect(parseChatEvent("null")).toBeNull()
    expect(parseChatEvent("42")).toBeNull()
    expect(parseChatEvent('{"message_id":5}')).toBeNull()
    expect(parseChatEvent('{"type":7}')).toBeNull()
  })

  it("ignores a type it doesn't know", () => {
    expect(parseChatEvent('{"type":"message.pinned","message_id":5}')).toBeNull()
  })
})
