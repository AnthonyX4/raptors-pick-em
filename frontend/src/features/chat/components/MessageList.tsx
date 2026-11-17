import { ArrowDown } from "lucide-react"
import { useLayoutEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import type { UserPrivate } from "@/features/auth/api"
import type { ChatMessage } from "../api"
import type { ChatActions } from "../hooks"
import { MessageItem } from "./MessageItem"

interface MessageListProps {
  messages: ChatMessage[]
  hasOlder: boolean
  loadingOlder: boolean
  onLoadOlder: () => void
  me: UserPrivate | null
  nowMs: number
  roomOpen: boolean
  actions: ChatActions
  empty: string
}

const NEAR_BOTTOM_PX = 48

// the scrolling part of the chat. it follows new messages only if the reader was already at the bottom (so
// reading older ones isn't interrupted, and a pill says there's more), and when older messages are added
// above it keeps what the reader was looking at where it was
export function MessageList({ messages, hasOlder, loadingOlder, onLoadOlder, me, nowMs, roomOpen, actions, empty }: MessageListProps) {
  const scroller = useRef<HTMLDivElement>(null)
  const atBottom = useRef(true)
  const seen = useRef<{ first: number | null; last: number | null; height: number }>({ first: null, last: null, height: 0 })
  const [unseen, setUnseen] = useState(false)

  const first = messages[0]?.message_id ?? null
  const last = messages.at(-1)?.message_id ?? null

  useLayoutEffect(() => {
    const el = scroller.current
    if (!el) return
    const before = seen.current
    if (before.first !== null && first !== null && first < before.first) {
      // older messages were added above: grow the scroll offset by what they added
      el.scrollTop += el.scrollHeight - before.height
    } else if (last !== before.last) {
      if (atBottom.current) {
        el.scrollTop = el.scrollHeight
      } else if (before.last !== null && last !== null && last > before.last) {
        setUnseen(true)
      }
    }
    seen.current = { first, last, height: el.scrollHeight }
  }, [first, last, messages])

  function onScroll() {
    const el = scroller.current
    if (!el) return
    atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
    if (atBottom.current) setUnseen(false)
  }

  function toBottom() {
    const el = scroller.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={scroller} onScroll={onScroll} className="h-full overflow-y-auto py-2">
        {hasOlder && (
          <div className="flex justify-center pb-2">
            <Button variant="ghost" size="sm" onClick={onLoadOlder} disabled={loadingOlder}>
              {loadingOlder ? "Loading…" : "Load earlier messages"}
            </Button>
          </div>
        )}
        {messages.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul>
            {messages.map((message) => (
              <MessageItem key={message.message_id} message={message} me={me} nowMs={nowMs} roomOpen={roomOpen} actions={actions} />
            ))}
          </ul>
        )}
      </div>
      {unseen && (
        <Button
          size="sm"
          onClick={toBottom}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 gap-1 rounded-full font-bold tracking-wide uppercase shadow-lg"
        >
          <ArrowDown className="size-3.5" />
          New messages
        </Button>
      )}
    </div>
  )
}
