import { errorMessage } from "@/features/auth/errors"
import { formatDateTime } from "@/lib/format"

// the api says "You're muted until 2026-11-17T21:30:00+00:00": say it in the reader's own time instead
export function chatErrorMessage(error: unknown): string {
  return errorMessage(error).replace(/(muted until )(\S+)/, (match, lead: string, iso: string) => {
    const when = new Date(iso)
    return Number.isNaN(when.getTime()) ? match : `${lead}${formatDateTime(when.toISOString())}`
  })
}
