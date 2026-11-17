import { Link, NavLink, Outlet } from "react-router"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/sonner"
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
  return (
    <div className="flex min-h-screen flex-col">
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
          {/* the account area becomes a user menu once auth exists (16.2) */}
          <div className="ml-auto flex items-center gap-6">
            <NavLink to="/login" className={navLinkClass}>
              Log in
            </NavLink>
            <Button asChild size="sm" className="font-bold uppercase tracking-wide">
              <Link to="/register">Sign up</Link>
            </Button>
          </div>
        </nav>
        {/* the links drop below the logo on a phone instead of a menu: three links fit */}
        <ul className="flex gap-6 border-t border-white/10 px-4 py-3 md:hidden">
          {links.map((link) => (
            <li key={link.to}>
              <NavLink to={link.to} end={link.end} className={navLinkClass}>
                {link.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </header>
      <main className="w-full flex-1 px-8 py-12 max-md:px-4 max-md:py-8">
        <Outlet />
      </main>
      <Toaster />
    </div>
  )
}
