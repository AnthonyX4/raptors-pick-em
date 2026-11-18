import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

// a placeholder block while something loads. the status role and the hidden text are what a screen reader
// gets instead of the grey box
export function Loading({ what, className }: { what: string; className?: string }) {
  return (
    <Skeleton role="status" aria-busy="true" className={className}>
      <span className="sr-only">Loading {what}…</span>
    </Skeleton>
  )
}

// a request that failed, with a way to ask again (the old "try refreshing the page" made people reload
// everything). role=alert so it is read out when it replaces a loading block
export function ErrorState({
  what,
  onRetry,
  retrying,
  className,
}: {
  what: string // "the schedule", "the chat": what couldn't be loaded
  onRetry: () => void
  retrying?: boolean
  className?: string
}) {
  return (
    <div role="alert" className={cn("flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground", className)}>
      <p>Couldn't load {what}.</p>
      <Button type="button" variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
        {retrying ? "Trying…" : "Try again"}
      </Button>
    </div>
  )
}
