import { useDocumentTitle } from "@/hooks/useDocumentTitle"

// the centred panel every auth page sits in, which also names the tab
export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string
  description?: string
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  useDocumentTitle(title)
  return (
    <div className="mx-auto w-full max-w-md rounded-md border border-border bg-card p-8 shadow-lg max-md:p-6">
      <h1 className="font-display text-4xl leading-none font-bold tracking-wide uppercase">{title}</h1>
      {description && <p className="mt-3 text-sm text-muted-foreground">{description}</p>}
      <div className="mt-6">{children}</div>
      {footer && <div className="mt-6 space-y-2 text-sm text-muted-foreground">{footer}</div>}
    </div>
  )
}

// an error from the server that isn't about one field
export function FormError({ message }: { message?: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {message}
    </p>
  )
}
