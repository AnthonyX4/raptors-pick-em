import { Link } from "react-router"
import { Button } from "@/components/ui/button"
import { useDocumentTitle } from "@/hooks/useDocumentTitle"

export function NotFoundPage() {
  useDocumentTitle("Page not found")
  return (
    <section className="py-16 text-center">
      <p aria-hidden className="font-display text-8xl leading-none font-bold text-primary">404</p>
      <h1 className="mt-4 font-display text-4xl leading-none font-bold tracking-wide uppercase">Page not found</h1>
      <p className="mt-3 text-muted-foreground">That page doesn't exist, or it moved.</p>
      <Button asChild className="mt-8 font-bold tracking-wide uppercase">
        <Link to="/">Back to the home page</Link>
      </Button>
    </section>
  )
}
