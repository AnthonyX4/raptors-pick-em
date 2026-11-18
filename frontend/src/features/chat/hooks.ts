import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useState } from "react"
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
import { mergeNewest, oldestId, prependOlder, remove, upsert, type ChatState } from "./state"
import { useChatSocket } from "./useChatSocket"

const REFRESH_MS = 30_000 // the newest page again, for what no event carries: the room opening and closing, renames, "[deleted]"

// the chat of one game, held in the query cache as one ChatState (see state.ts for how it changes).
// three things keep it current: the query itself, which refetches the newest page every 30s and merges it
// in; the room's websocket (useChatSocket), which applies each event the moment it arrives while the room is
// open; and loadOlder, for scrolling back
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

  const { reconnecting } = useChatSocket(gameId, query.data?.roomOpen ?? false)

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

  return {
    chat: query.data,
    isPending: query.isPending,
    isError: query.isError,
    refetch: query.refetch,
    isFetching: query.isFetching,
    reconnecting,
    loadOlder,
    loadingOlder,
  }
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
