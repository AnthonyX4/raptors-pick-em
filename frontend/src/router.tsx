import { createBrowserRouter } from "react-router"
import { AppShell } from "@/components/layout/AppShell"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage"
import { GameDetailPage } from "@/pages/GameDetailPage"
import { GamesPage } from "@/pages/GamesPage"
import { HomePage } from "@/pages/HomePage"
import { LeaderboardPage } from "@/pages/LeaderboardPage"
import { LoginPage } from "@/pages/LoginPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { ProfilePage } from "@/pages/ProfilePage"
import { RegisterPage } from "@/pages/RegisterPage"
import { ResetPasswordPage } from "@/pages/ResetPasswordPage"
import { SettingsPage } from "@/pages/SettingsPage"

// /games/:gameId and /reset-password are linked from the backend's emails: don't rename them
export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/games", element: <GamesPage /> },
      { path: "/games/:gameId", element: <GameDetailPage /> },
      { path: "/leaderboard", element: <LeaderboardPage /> },
      { path: "/users/:userId", element: <ProfilePage /> },
      { element: <ProtectedRoute />, children: [{ path: "/settings", element: <SettingsPage /> }] },
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
])
