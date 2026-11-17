import { Link } from "react-router"
import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <section className="py-16 text-center">
      <p className="text-6xl font-bold text-primary">404</p>
      <h1 className="mt-4 text-2xl font-bold tracking-tight">Page not found</h1>
      <p className="mt-2 text-muted-foreground">That page doesn't exist, or it moved.</p>
      <Button asChild className="mt-6">
        <Link to="/">Back to the home page</Link>
      </Button>
    </section>
  )
}
