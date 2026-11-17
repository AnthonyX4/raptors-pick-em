import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

export type ChatMessage = components["schemas"]["ChatMessageResponse"]
export type ChatPage = components["schemas"]["ChatMessagePage"]
export type ChatUser = components["schemas"]["UserPublic"]
export type Mute = components["schemas"]["MuteResponse"]

// no cursor: the newest page. before: the page just older than that message id. after: what's newer than it
export const fetchMessages = (gameId: string, cursor: { before?: number; after?: number } = {}) =>
  api.get<ChatPage>(`/api/games/${gameId}/messages`, { query: cursor })

export const postMessage = (gameId: string, body: string) =>
  api.post<ChatMessage>(`/api/games/${gameId}/messages`, { body })

export const editMessage = (messageId: number, body: string) =>
  api.patch<ChatMessage>(`/api/messages/${messageId}`, { body })

export const deleteMessage = (messageId: number) => api.delete(`/api/messages/${messageId}`)

// both answer with the updated message, like count included
export const likeMessage = (messageId: number) => api.put<ChatMessage>(`/api/messages/${messageId}/like`)
export const unlikeMessage = (messageId: number) => api.delete<ChatMessage>(`/api/messages/${messageId}/like`)

// admins only: any message, and a timed mute on its author
export const adminDeleteMessage = (messageId: number) => api.delete(`/api/admin/messages/${messageId}`)

export const muteUser = (userId: number, hours: number, reason: string | null) =>
  api.put<Mute>(`/api/admin/users/${userId}/mute`, { hours, reason })
