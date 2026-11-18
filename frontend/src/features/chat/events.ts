import type { ChatMessage } from "./api"

// what the chat's websocket sends. websocket routes aren't in the openapi schema, so these are written by hand
// to match the event models in Backend/schemas.py (the one exception to "types come from the backend");
// message.created reuses the generated ChatMessage
export type ChatEvent =
  | { type: "message.created"; message: ChatMessage }
  | { type: "message.edited"; message_id: number; body: string; edited_at: string }
  | { type: "message.deleted"; message_id: number }
  | { type: "message.likes"; message_id: number; like_count: number } // the total, not a delta

const EVENT_TYPES: string[] = ["message.created", "message.edited", "message.deleted", "message.likes"]

// the text of one websocket frame, or null when it isn't an event we know. an unknown type is ignored rather
// than an error, so a newer backend can add events without breaking an open tab
export function parseChatEvent(text: string): ChatEvent | null {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof data !== "object" || data === null || !("type" in data)) return null
  if (typeof data.type !== "string" || !EVENT_TYPES.includes(data.type)) return null
  return data as ChatEvent // only the type is checked: the backend is the one sending the rest
}
