import { createBrowserRouter } from "react-router"
import { AppShell } from "@/components/layout/AppShell"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { Loading } from "@/components/states"
import { RouteErrorPage } from "@/pages/RouteErrorPage"

// each page is its own chunk, fetched when it is first visited, so the first load carries the shell and the
// page asked for instead of the whole app. react router waits for the chunk before it switches page
const page = (load: () => Promise<Record<string, React.ComponentType>>, name: string) => async () => ({
  Component: (await load())[name],
})

// /games/:gameId and /reset-password are linked from the backend's emails: don't rename them
export const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteErrorPage />, // a page that crashes while rendering, or whose chunk is gone after a deploy
    hydrateFallbackElement: <Loading what="the page" className="m-8 h-64" />, // the first load, until the page's chunk arrives
    children: [
      { path: "/", lazy: page(() => import("@/pages/HomePage"), "HomePage") },
      { path: "/games", lazy: page(() => import("@/pages/GamesPage"), "GamesPage") },
      { path: "/games/:gameId", lazy: page(() => import("@/pages/GameDetailPage"), "GameDetailPage") },
      { path: "/leaderboard", lazy: page(() => import("@/pages/LeaderboardPage"), "LeaderboardPage") },
      { path: "/users/:userId", lazy: page(() => import("@/pages/ProfilePage"), "ProfilePage") },
      { element: <ProtectedRoute />, children: [{ path: "/settings", lazy: page(() => import("@/pages/SettingsPage"), "SettingsPage") }] },
      { path: "/login", lazy: page(() => import("@/pages/LoginPage"), "LoginPage") },
      { path: "/register", lazy: page(() => import("@/pages/RegisterPage"), "RegisterPage") },
      { path: "/forgot-password", lazy: page(() => import("@/pages/ForgotPasswordPage"), "ForgotPasswordPage") },
      { path: "/reset-password", lazy: page(() => import("@/pages/ResetPasswordPage"), "ResetPasswordPage") },
      { path: "*", lazy: page(() => import("@/pages/NotFoundPage"), "NotFoundPage") },
    ],
  },
])
