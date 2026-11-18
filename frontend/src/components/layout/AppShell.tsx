import { useEffect, useRef } from "react"
import { Link, NavLink, Outlet, ScrollRestoration, useLocation } from "react-router"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/sonner"
import { UserMenu } from "@/features/auth/components/UserMenu"
import { useAuth } from "@/features/auth/useAuth"
import { cn } from "@/lib/utils"

const links = [
  { to: "/", label: "Home", end: true },
  { to: "/games", label: "Games", end: false },
  { to: "/leaderboard", label: "Leaderboard", end: false },
]

// plain text that brightens: no pill or background on hover or on the current page
const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "text-sm font-bold uppercase tracking-wide transition-colors hover:text-white",
    isActive ? "text-white" : "text-white/60",
  )

export function AppShell() {
  const { user, isLoading } = useAuth()
  const main = useRef<HTMLElement>(null)
  const { pathname } = useLocation()
  const firstPath = useRef(pathname)

  // a client-side navigation keeps focus on the link that was clicked, which is now gone or off screen, and
  // tells a screen reader nothing. moving focus to the page makes the next Tab start there and has the new
  // page announced. not on first load (the browser already starts at the top) and not for a query change
  useEffect(() => {
    if (pathname === firstPath.current) return
    firstPath.current = pathname
    main.current?.focus({ preventScroll: true })
  }, [pathname])

  return (
    <div className="flex min-h-screen flex-col">
      {/* first stop for a keyboard: past the navbar to the page */}
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-4 py-2 text-sm font-bold tracking-wide text-primary-foreground uppercase focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <header className="bg-black">
        <nav className="flex h-20 items-center gap-12 px-8 max-md:h-16 max-md:px-4" aria-label="Main">
          <Link to="/" aria-label="Raptors Pick'em home" className="shrink-0">
            <img src="/raptors-logo.svg" alt="" className="size-12 max-md:size-10" />
          </Link>
          <ul className="flex gap-10 max-md:hidden">
            {links.map((link) => (
              <li key={link.to}>
                <NavLink to={link.to} end={link.end} className={navLinkClass}>
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
          {/* empty while a stored token is being checked, so "Log in" doesn't flash for a logged-in person */}
          <div className="ml-auto flex items-center gap-6">
            {isLoading ? null : user ? (
              <UserMenu user={user} />
            ) : (
              <>
                <NavLink to="/login" className={navLinkClass}>
                  Log in
                </NavLink>
                <Button asChild size="sm" className="font-bold uppercase tracking-wide">
                  <Link to="/register">Sign up</Link>
                </Button>
              </>
            )}
          </div>
        </nav>
        {/* the links drop below the logo on a phone instead of a menu: three links fit */}
        <nav aria-label="Pages" className="border-t border-white/10 px-4 py-3 md:hidden">
          <ul className="flex gap-6">
            {links.map((link) => (
              <li key={link.to}>
                <NavLink to={link.to} end={link.end} className={navLinkClass}>
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main ref={main} id="main" tabIndex={-1} className="w-full flex-1 px-8 py-12 outline-none max-md:px-4 max-md:py-8">
        <Outlet />
      </main>
      <Toaster />
      {/* back to the top on a new page, and to where you were on back and forward */}
      <ScrollRestoration />
    </div>
  )
}
