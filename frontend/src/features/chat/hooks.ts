import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { ApiError } from "@/lib/api-client"
import {
  adminDeleteMessage,
  deleteMessage,
  editMessage,
  fetchMessages,
  likeMessage,
  muteUser,
  postMessage,
  unlikeMessage,
} from "./api"
import { chatErrorMessage } from "./errors"
import { chatKey } from "./keys"
import { appendNew, mergeNewest, newestId, oldestId, prependOlder, remove, upsert, type ChatState } from "./state"

const POLL_MS = 3_000 // new messages, while the room is open
const REFRESH_MS = 30_000 // the newest page again, for other people's edits, deletes and likes
const MAX_CATCH_UP_PAGES = 10 // a tab that was hidden for ages doesn't fetch the whole room in one go

const visible = () => document.visibilityState === "visible"

// the chat of one game, held in the query cache as one ChatState (see state.ts for how it changes).
// three things keep it current: the query itself, which refetches the newest page every 30s and merges it
// in; a 3s poll for messages newer than the newest one, only while the room is open and the tab is showing;
// and loadOlder, for scrolling back
export function useGameChat(gameId: string) {
  const queryClient = useQueryClient()
  const key = chatKey(gameId)
  const [loadingOlder, setLoadingOlder] = useState(false)

  const query = useQuery({
    queryKey: key,
    // merging into what's cached, rather than replacing it, keeps the older messages that were scrolled back to
    queryFn: async () => mergeNewest(queryClient.getQueryData<ChatState>(key), await fetchMessages(gameId)),
    refetchInterval: REFRESH_MS,
  })

  const roomOpen = query.data?.roomOpen ?? false
  useEffect(() => {
    if (!roomOpen) return
    let busy = false
    let stopped = false

    async function poll() {
      if (busy || !visible()) return
      busy = true
      try {
        for (let i = 0; i < MAX_CATCH_UP_PAGES; i++) {
          const state = queryClient.getQueryData<ChatState>(key)
          if (!state) return
          const page = await fetchMessages(gameId, { after: newestId(state) })
          if (stopped) return
          queryClient.setQueryData<ChatState>(key, (current) => current && appendNew(current, page))
          if (!page.has_newer) return
        }
      } catch {
        // a failed poll is just tried again in 3 seconds
      } finally {
        busy = false
      }
    }

    const timer = setInterval(() => void poll(), POLL_MS)
    // a tab coming back to the front catches up at once instead of waiting for the next tick
    const onVisible = () => {
      if (!visible()) return
      void poll()
      void queryClient.invalidateQueries({ queryKey: key })
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => {
      stopped = true
      clearInterval(timer)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [roomOpen, gameId, key, queryClient])

  const loadOlder = useCallback(async () => {
    const state = queryClient.getQueryData<ChatState>(key)
    const before = state && oldestId(state)
    if (!state || before === null || loadingOlder) return
    setLoadingOlder(true)
    try {
      const page = await fetchMessages(gameId, { before })
      queryClient.setQueryData<ChatState>(key, (current) => current && prependOlder(current, page))
    } catch (error) {
      toast.error(chatErrorMessage(error))
    } finally {
      setLoadingOlder(false)
    }
  }, [gameId, key, loadingOlder, queryClient])

  return { chat: query.data, isPending: query.isPending, isError: query.isError, loadOlder, loadingOlder }
}

// everything a person can do to a message. each action applies the api's answer to the cached chat straight
// away. a 404 or 409 usually means the room or the message changed under them, so those refetch the page
export function useChatActions(gameId: string) {
  const queryClient = useQueryClient()
  const key = chatKey(gameId)

  const change = (apply: (state: ChatState) => ChatState) =>
    queryClient.setQueryData<ChatState>(key, (state) => state && apply(state))

  const resync = (error: unknown) => {
    if (error instanceof ApiError && (error.status === 404 || error.status === 409)) {
      void queryClient.invalidateQueries({ queryKey: key })
    }
  }

  // send and edit report their error where the person is typing; the rest say it in a toast
  const failed = (error: unknown) => {
    resync(error)
    toast.error(chatErrorMessage(error))
  }

  return {
    send: useMutation({
      mutationFn: (body: string) => postMessage(gameId, body),
      onSuccess: (message) => change((state) => upsert(state, message)),
      onError: resync,
    }),
    edit: useMutation({
      mutationFn: ({ messageId, body }: { messageId: number; body: string }) => editMessage(messageId, body),
      onSuccess: (message) => change((state) => upsert(state, message)),
      onError: resync,
    }),
    like: useMutation({
      mutationFn: ({ messageId, liked }: { messageId: number; liked: boolean }) =>
        liked ? likeMessage(messageId) : unlikeMessage(messageId),
      onSuccess: (message) => change((state) => upsert(state, message)),
      onError: failed,
    }),
    remove: useMutation({
      mutationFn: ({ messageId, asAdmin }: { messageId: number; asAdmin: boolean }) =>
        asAdmin ? adminDeleteMessage(messageId) : deleteMessage(messageId),
      onSuccess: (_, { messageId }) => change((state) => remove(state, messageId)),
      onError: failed,
    }),
    // no toast on error: the mute dialog shows it
    mute: useMutation({
      mutationFn: ({ userId, hours, reason }: { userId: number; hours: number; reason: string | null }) =>
        muteUser(userId, hours, reason),
    }),
  }
}

export type ChatActions = ReturnType<typeof useChatActions>
