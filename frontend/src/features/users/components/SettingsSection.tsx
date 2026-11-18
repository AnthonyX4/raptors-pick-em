import { cn } from "@/lib/utils"

// one card of the settings page
export function SettingsSection({
  title,
  description,
  danger,
  children,
}: {
  title: string
  description?: string
  danger?: boolean
  children: React.ReactNode
}) {
  return (
    <section className={cn("rounded-md border bg-card p-8 max-md:p-5", danger ? "border-destructive/40" : "border-border")}>
      <h2 className="font-display text-2xl leading-none font-bold tracking-wide uppercase">{title}</h2>
      {description && <p className="mt-2 text-sm text-muted-foreground">{description}</p>}
      <div className="mt-6">{children}</div>
    </section>
  )
}
