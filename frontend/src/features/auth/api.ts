import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

export type UserPrivate = components["schemas"]["UserPrivate"]
type Token = components["schemas"]["Token"]
type MessageResponse = components["schemas"]["MessageResponse"]

export const login = (email: string, password: string) => api.login<Token>(email, password)

export const register = (body: { username: string; email: string; password: string }) =>
  api.post<UserPrivate>("/api/users", body)

export const fetchMe = () => api.get<UserPrivate>("/api/users/me")

export const forgotPassword = (email: string) =>
  api.post<MessageResponse>("/api/users/forgot-password", { email })

export const resetPassword = (token: string, newPassword: string) =>
  api.post<MessageResponse>("/api/users/reset-password", { token, new_password: newPassword })
