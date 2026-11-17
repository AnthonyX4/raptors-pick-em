import { useLocation } from "react-router"

// where a person was headed before ProtectedRoute sent them to log in. it comes from router state, which
// only our own <Navigate> sets, but it's still checked to be a local path
export function useReturnTo(): string {
  const state = useLocation().state as { from?: { pathname?: string; search?: string; hash?: string } } | null
  const from = state?.from
  if (!from?.pathname || !from.pathname.startsWith("/") || from.pathname.startsWith("//")) return "/"
  return `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`
}
