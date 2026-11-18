import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { parseChatEvent } from "./events"
import { chatKey } from "./keys"
import { applyEvent, type ChatState } from "./state"

const FIRST_RETRY_MS = 1_000
const MAX_RETRY_MS = 30_000

// 1s, 2s, 4s, 8s ... then 30s between tries, so a down api isn't hammered by every open tab
const retryDelay = (attempt: number) => Math.min(FIRST_RETRY_MS * 2 ** attempt, MAX_RETRY_MS)

// relative to the page like every other call, so the same code works behind vite's proxy and nginx
const socketUrl = (gameId: string) =>
  `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/games/${gameId}/ws`

// keeps the game's cached chat current from the room's websocket, while `enabled` (the room is open). the
// socket only delivers: sending, editing and liking stay plain requests (see useChatActions).
// every time it opens, the first time included, the chat is refetched, which fills in whatever was missed
// while it was down (new messages, but also edits, deletes and likes); that and the retries are the only
// recovery, there is no polling fallback
export function useChatSocket(gameId: string, enabled: boolean) {
  const queryClient = useQueryClient()
  const [reconnecting, setReconnecting] = useState(false)

  useEffect(() => {
    if (!enabled) return
    const key = chatKey(gameId)
    let socket: WebSocket | null = null
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let attempt = 0
    let stopped = false

    function connect() {
      const current = new WebSocket(socketUrl(gameId))
      socket = current
      current.onopen = () => {
        attempt = 0
        setReconnecting(false)
        void queryClient.invalidateQueries({ queryKey: key })
      }
      current.onmessage = (frame) => {
        const event = typeof frame.data === "string" ? parseChatEvent(frame.data) : null
        if (!event) return
        queryClient.setQueryData<ChatState>(key, (state) => state && applyEvent(state, event))
      }
      current.onclose = () => {
        if (stopped) return // closed by the cleanup below, not by the network
        setReconnecting(true)
        retryTimer = setTimeout(connect, retryDelay(attempt))
        attempt += 1
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(retryTimer)
      socket?.close()
      setReconnecting(false)
    }
  }, [enabled, gameId, queryClient])

  return { reconnecting }
}
