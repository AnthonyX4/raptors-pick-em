import { describe, expect, it } from "vitest"
import type { ChatMessage, ChatPage } from "./api"
import { appendNew, fromPage, mergeNewest, newestId, oldestId, prependOlder, remove, upsert } from "./state"

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

describe("appendNew", () => {
  it("adds only the messages it doesn't hold", () => {
    const held = fromPage(page([5, 6]))
    expect(ids(appendNew(held, page([6, 7, 8])))).toEqual([5, 6, 7, 8])
  })

  it("returns the same state when nothing changed", () => {
    const held = fromPage(page([5, 6]))
    expect(appendNew(held, page([]))).toBe(held)
  })

  it("notices the room closing", () => {
    const held = fromPage(page([5]))
    expect(appendNew(held, page([], { room_open: false })).roomOpen).toBe(false)
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
