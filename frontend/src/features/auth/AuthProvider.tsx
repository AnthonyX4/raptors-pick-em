import { useCallback, useEffect, useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { clearToken, getToken, setAuthResetHandler, setToken } from "@/lib/api-client"
import { fetchMe, login as loginRequest, register as registerRequest } from "./api"
import { AuthContext, type AuthContextValue } from "./auth-context"
import { meKey } from "./keys"

// context holds only who is logged in and the actions. the user itself is server data, so it lives in
// the query cache under ["me"]; the token's presence is what switches that query on
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [hasToken, setHasToken] = useState(() => getToken() !== null)

  const me = useQuery({
    queryKey: meKey,
    queryFn: fetchMe,
    enabled: hasToken,
    staleTime: Infinity, // refreshed by login/logout, not by the clock
  })

  // the api client calls this when it dropped a token the server refused (expired, or the account is gone)
  useEffect(() => {
    setAuthResetHandler(() => {
      setHasToken(false)
      queryClient.removeQueries({ queryKey: meKey })
      toast("Your session expired. Please log in again.")
    })
    return () => setAuthResetHandler(null)
  }, [queryClient])

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await loginRequest(email, password)
      setToken(access_token)
      try {
        await queryClient.fetchQuery({ queryKey: meKey, queryFn: fetchMe, staleTime: 0 })
      } catch (error) {
        clearToken()
        throw error
      }
      setHasToken(true)
      // everything fetched while logged out is stale now: liked_by_me, picks, and so on
      await queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== meKey[0] })
    },
    [queryClient],
  )

  const register = useCallback(
    async (values: { username: string; email: string; password: string }) => {
      await registerRequest(values)
      await login(values.email, values.password)
    },
    [login],
  )

  const logout = useCallback(() => {
    clearToken()
    setHasToken(false)
    queryClient.clear() // nothing of the last user may survive in the cache
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: hasToken ? (me.data ?? null) : null,
      isLoading: hasToken && me.isPending,
      login,
      register,
      logout,
    }),
    [hasToken, me.data, me.isPending, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
