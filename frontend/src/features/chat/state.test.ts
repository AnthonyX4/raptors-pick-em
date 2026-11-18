import { describe, expect, it } from "vitest"
import type { ChatMessage, ChatPage } from "./api"
import type { ChatEvent } from "./events"
import { applyEvent, fromPage, mergeNewest, newestId, oldestId, prependOlder, remove, upsert } from "./state"

const message = (id: number, extra: Partial<ChatMessage> = {}): ChatMessage => ({
  message_id: id,
  game_id: "g1",
  author: null,
  body: `message ${id}`,
  created_at: "2026-11-17T20:00:00Z",
  edited_at: null,
  editable_until: "2026-11-17T20:05:00Z",
  like_count: 0,
  liked_by_me: false,
  ...extra,
})

const page = (ids: number[], extra: Partial<ChatPage> = {}): ChatPage => ({
  messages: ids.map((id) => message(id)),
  has_older: false,
  has_newer: false,
  room_open: true,
  opens_at: "2026-11-17T00:00:00Z",
  closes_at: null,
  ...extra,
})

const ids = (state: { messages: ChatMessage[] }) => state.messages.map((m) => m.message_id)

describe("mergeNewest", () => {
  it("starts from the page when nothing is held", () => {
    expect(ids(mergeNewest(undefined, page([5, 6, 7])))).toEqual([5, 6, 7])
  })

  it("takes edits, likes and new messages from the page", () => {
    const held = fromPage(page([5, 6, 7]))
    const next = mergeNewest(held, {
      ...page([]),
      messages: [message(5), message(6, { body: "fixed", edited_at: "x", like_count: 3 }), message(7), message(8)],
    })
    expect(ids(next)).toEqual([5, 6, 7, 8])
    expect(next.messages[1]).toMatchObject({ body: "fixed", like_count: 3 })
  })

  it("drops a message inside the page's range that's gone", () => {
    const held = fromPage(page([5, 6, 7]))
    expect(ids(mergeNewest(held, page([5, 7])))).toEqual([5, 7])
  })

  it("drops the newest held message when it was deleted", () => {
    const held = fromPage(page([5, 6, 7]))
    expect(ids(mergeNewest(held, page([5, 6])))).toEqual([5, 6])
  })

  it("keeps older messages scrolled back to, and their has_older", () => {
    const held = { ...fromPage(page([1, 2, 5, 6])), hasOlder: true }
    const next = mergeNewest(held, page([5, 6, 7], { has_older: true }))
    expect(ids(next)).toEqual([1, 2, 5, 6, 7])
    expect(next.hasOlder).toBe(true)
  })

  it("takes has_older from the page when nothing older is held", () => {
    const held = fromPage(page([5, 6], { has_older: true }))
    expect(mergeNewest(held, page([5, 6], { has_older: false })).hasOlder).toBe(false)
  })

  it("starts over rather than leave a hole when a whole page arrived in between", () => {
    const held = fromPage(page([1, 2, 3]))
    const next = mergeNewest(held, page([60, 61, 62], { has_older: true }))
    expect(ids(next)).toEqual([60, 61, 62])
    expect(next.hasOlder).toBe(true)
  })

  it("follows the room opening and closing", () => {
    const held = fromPage(page([5], { room_open: false }))
    expect(mergeNewest(held, page([5], { room_open: true })).roomOpen).toBe(true)
  })

  it("empties when every message was deleted", () => {
    expect(ids(mergeNewest(fromPage(page([5, 6])), page([])))).toEqual([])
  })
})

describe("applyEvent", () => {
  const edited = (id: number): ChatEvent => ({ type: "message.edited", message_id: id, body: "fixed", edited_at: "x" })
  const likes = (id: number, count: number): ChatEvent => ({ type: "message.likes", message_id: id, like_count: count })
  const deleted = (id: number): ChatEvent => ({ type: "message.deleted", message_id: id })

  it("adds a created message in id order", () => {
    const held = fromPage(page([5, 7]))
    expect(ids(applyEvent(held, { type: "message.created", message: message(6) }))).toEqual([5, 6, 7])
  })

  it("ignores a created message that is already held, keeping what you did to it", () => {
    const held = fromPage(page([5]))
    const liked = upsert(held, message(5, { like_count: 1, liked_by_me: true }))
    const next = applyEvent(liked, { type: "message.created", message: message(5) })
    expect(next).toBe(liked)
    expect(next.messages[0]).toMatchObject({ like_count: 1, liked_by_me: true })
  })

  it("changes only the body and edited_at on an edit", () => {
    const held = upsert(fromPage(page([5, 6])), message(6, { like_count: 2, liked_by_me: true }))
    const next = applyEvent(held, edited(6))
    expect(next.messages[1]).toMatchObject({ body: "fixed", edited_at: "x", like_count: 2, liked_by_me: true })
    expect(next.messages[0]).toBe(held.messages[0])
  })

  it("removes a deleted message", () => {
    expect(ids(applyEvent(fromPage(page([5, 6, 7])), deleted(6)))).toEqual([5, 7])
  })

  it("sets the like count and keeps liked_by_me", () => {
    const held = upsert(fromPage(page([5])), message(5, { like_count: 1, liked_by_me: true }))
    expect(applyEvent(held, likes(5, 4)).messages[0]).toMatchObject({ like_count: 4, liked_by_me: true })
  })

  it("returns the same state for a message it doesn't hold", () => {
    const held = fromPage(page([5]))
    expect(applyEvent(held, edited(99))).toBe(held)
    expect(applyEvent(held, deleted(99))).toBe(held)
    expect(applyEvent(held, likes(99, 3))).toBe(held)
  })

  it("applies the same like total twice to the same result", () => {
    const once = applyEvent(fromPage(page([5])), likes(5, 3))
    expect(applyEvent(once, likes(5, 3)).messages).toEqual(once.messages)
  })
})

describe("prependOlder", () => {
  it("puts older messages first and takes has_older from the page", () => {
    const held = { ...fromPage(page([5, 6])), hasOlder: true }
    const next = prependOlder(held, page([3, 4], { has_older: true }))
    expect(ids(next)).toEqual([3, 4, 5, 6])
    expect(next.hasOlder).toBe(true)
    expect(prependOlder(next, page([1, 2])).hasOlder).toBe(false)
  })
})

describe("upsert and remove", () => {
  it("replaces a held message with the response", () => {
    const held = fromPage(page([5, 6, 7]))
    const next = upsert(held, message(6, { like_count: 1, liked_by_me: true }))
    expect(ids(next)).toEqual([5, 6, 7])
    expect(next.messages[1]).toMatchObject({ liked_by_me: true })
  })

  it("adds your own new message in id order", () => {
    expect(ids(upsert(fromPage(page([5, 6])), message(7)))).toEqual([5, 6, 7])
  })

  it("removes a message", () => {
    expect(ids(remove(fromPage(page([5, 6, 7])), 6))).toEqual([5, 7])
  })
})

describe("cursors", () => {
  it("reads the oldest and newest ids", () => {
    const state = fromPage(page([5, 6, 7]))
    expect(oldestId(state)).toBe(5)
    expect(newestId(state)).toBe(7)
  })

  it("asks for everything when empty", () => {
    expect(newestId(fromPage(page([])))).toBe(0)
    expect(oldestId(fromPage(page([])))).toBeNull()
  })
})
