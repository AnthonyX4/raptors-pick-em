import type { UserPrivate } from "@/features/auth/api"
import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

export type UserPublic = components["schemas"]["UserPublic"]
type MessageResponse = components["schemas"]["MessageResponse"]

// what the api lets one user see of another: a name and a picture
export const fetchUser = (userId: number) => api.get<UserPublic>(`/api/users/${userId}`)

// every field is optional; changing the email also needs current_password. all answer with the whole user
export interface ProfileUpdate {
  username?: string
  email?: string
  current_password?: string
  email_reminders?: boolean
}
export const updateUser = (userId: number, body: ProfileUpdate) => api.patch<UserPrivate>(`/api/users/${userId}`, body)

export const changePassword = (currentPassword: string, newPassword: string) =>
  api.patch<MessageResponse>("/api/users/me/password", { current_password: currentPassword, new_password: newPassword })

export const uploadPicture = (userId: number, file: File) => {
  const body = new FormData()
  body.append("file", file)
  return api.upload<UserPrivate>(`/api/users/${userId}/picture`, body)
}

export const deletePicture = (userId: number) => api.delete<UserPrivate>(`/api/users/${userId}/picture`)

export const deleteAccount = (userId: number) => api.delete(`/api/users/${userId}`)
