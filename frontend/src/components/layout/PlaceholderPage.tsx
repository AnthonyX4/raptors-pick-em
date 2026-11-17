// stands in for a page until its sub-step builds it
export function PlaceholderPage({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <section>
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-muted-foreground">Coming soon.</p>
      {children}
    </section>
  )
}
