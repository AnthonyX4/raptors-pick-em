import { isRouteErrorResponse, useRouteError } from "react-router"
import { Button } from "@/components/ui/button"
import { useDocumentTitle } from "@/hooks/useDocumentTitle"

// what shows when a page crashes while rendering, instead of react router's developer error screen.
// it is the router's errorElement, so it replaces the whole tree; the buttons are plain, full page loads
// because a client-side link would stay inside whatever broke
export function RouteErrorPage() {
  const error = useRouteError()
  useDocumentTitle("Something went wrong")
  if (!isRouteErrorResponse(error)) console.error(error)

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-start justify-center px-6">
      <h1 className="font-display text-5xl leading-none font-bold tracking-wide uppercase">Something went wrong</h1>
      <p className="mt-4 text-muted-foreground">
        This page hit an error it couldn't recover from. Reloading usually fixes it, and your picks and messages are
        safe on the server.
      </p>
      <div className="mt-8 flex gap-3">
        <Button className="font-bold tracking-wide uppercase" onClick={() => window.location.reload()}>
          Reload
        </Button>
        <Button asChild variant="outline" className="font-bold tracking-wide uppercase">
          <a href="/">Home</a>
        </Button>
      </div>
    </main>
  )
}
