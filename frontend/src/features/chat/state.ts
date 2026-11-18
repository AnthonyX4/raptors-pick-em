import type { ChatMessage, ChatPage } from "./api"
import type { ChatEvent } from "./events"

// the chat of one game as the page holds it, and the pure rules for changing it. kept apart from react
// so the merging (the part that's easy to get subtly wrong) can be tested without a browser
export interface ChatState {
  messages: ChatMessage[] // oldest first, one entry per message_id
  hasOlder: boolean
  hasNewer: boolean
  roomOpen: boolean
  opensAt: string
  closesAt: string | null
}

export const oldestId = (state: ChatState) => state.messages[0]?.message_id ?? null
export const newestId = (state: ChatState) => state.messages.at(-1)?.message_id ?? 0 // 0: "everything is newer"

export function fromPage(page: ChatPage): ChatState {
  return {
    messages: page.messages,
    hasOlder: page.has_older,
    hasNewer: page.has_newer,
    roomOpen: page.room_open,
    opensAt: page.opens_at,
    closesAt: page.closes_at,
  }
}

const room = (page: ChatPage) => ({ roomOpen: page.room_open, opensAt: page.opens_at, closesAt: page.closes_at })

// the newest page, fetched every so often. it is the truth for the ids it covers, so inside that range
// edits, like counts and deletes all come from it; older messages that were scrolled back to are kept.
// if nothing loaded reaches the page (more than a page of messages arrived meanwhile) the old ones can't be
// joined to it without a hole in the middle, so they are dropped and can be scrolled back to again
export function mergeNewest(state: ChatState | undefined, page: ChatPage): ChatState {
  if (!state || state.messages.length === 0 || page.messages.length === 0) return fromPage(page)
  const firstInPage = page.messages[0].message_id
  if (newestId(state) < firstInPage) return fromPage(page)

  const older = state.messages.filter((message) => message.message_id < firstInPage)
  return {
    messages: [...older, ...page.messages],
    hasOlder: older.length > 0 ? state.hasOlder : page.has_older,
    hasNewer: page.has_newer,
    ...room(page),
  }
}

// the page just older than the oldest one held (scrolling back)
export function prependOlder(state: ChatState, page: ChatPage): ChatState {
  const known = new Set(state.messages.map((message) => message.message_id))
  const added = page.messages.filter((message) => !known.has(message.message_id))
  return { ...state, messages: [...added, ...state.messages], hasOlder: page.has_older }
}

// your own post, edit or like, applied from the response: replaces the message if it's held, else adds it
export function upsert(state: ChatState, message: ChatMessage): ChatState {
  const held = state.messages.some((m) => m.message_id === message.message_id)
  const messages = held
    ? state.messages.map((m) => (m.message_id === message.message_id ? message : m))
    : [...state.messages, message].sort((a, b) => a.message_id - b.message_id)
  return { ...state, messages }
}

export function remove(state: ChatState, messageId: number): ChatState {
  return { ...state, messages: state.messages.filter((m) => m.message_id !== messageId) }
}

const holds = (state: ChatState, messageId: number) => state.messages.some((m) => m.message_id === messageId)

// one event from the room's websocket. an event about a message that isn't held changes nothing, and so does
// a repeat of one already applied: the same state comes back, so the list doesn't re-render for nothing
export function applyEvent(state: ChatState, event: ChatEvent): ChatState {
  switch (event.type) {
    case "message.created":
      // not upsert: your own post's response may have arrived first, and if you've since liked it, the
      // event's "no likes yet" copy would undo that
      return holds(state, event.message.message_id) ? state : upsert(state, event.message)
    case "message.deleted":
      return holds(state, event.message_id) ? remove(state, event.message_id) : state
    case "message.edited":
      return patch(state, event.message_id, { body: event.body, edited_at: event.edited_at })
    case "message.likes":
      // liked_by_me stays as it is: an event never says who liked
      return patch(state, event.message_id, { like_count: event.like_count })
  }
}

function patch(state: ChatState, messageId: number, changes: Partial<ChatMessage>): ChatState {
  if (!holds(state, messageId)) return state
  return { ...state, messages: state.messages.map((m) => (m.message_id === messageId ? { ...m, ...changes } : m)) }
}
