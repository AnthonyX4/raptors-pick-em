import { createContext } from "react"
import type { UserPrivate } from "./api"

export interface AuthContextValue {
  user: UserPrivate | null
  isLoading: boolean // true while a stored token is being checked against /me
  login: (email: string, password: string) => Promise<void>
  register: (values: { username: string; email: string; password: string }) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
