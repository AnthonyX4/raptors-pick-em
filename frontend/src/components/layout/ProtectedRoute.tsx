import { useRef } from "react"
import { Navigate, Outlet, useLocation } from "react-router"
import { useAuth } from "@/features/auth/useAuth"

// waits for the startup /me call so a refresh on /settings doesn't bounce a logged-in person to /login
export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  const hadUser = useRef(false)

  if (isLoading) return <p className="text-muted-foreground">Loading…</p>
  if (user) hadUser.current = true
  if (!user) {
    // a visitor who never logged in is asked to; someone who just logged out (or whose session expired)
    // while on this page goes home, since the login form is not what they asked for
    return hadUser.current ? <Navigate to="/" replace /> : <Navigate to="/login" replace state={{ from: location }} />
  }
  return <Outlet />
}
