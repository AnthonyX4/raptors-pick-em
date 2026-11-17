// the api speaks utc only; everything is shown in the browser's own time zone

const dateTime = new Intl.DateTimeFormat(undefined, {
  weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
})
const date = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" })
const time = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" })

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso))
export const formatDate = (iso: string) => date.format(new Date(iso))
export const formatTime = (iso: string) => time.format(new Date(iso))

// a score that isn't known yet (scheduled game) shows as a dash
export function formatScore(home: number | null | undefined, away: number | null | undefined) {
  if (home == null || away == null) return "–"
  return `${home}–${away}`
}

// the nba counts 1-4, then overtimes: 5 is the first overtime
export function formatPeriod(period: number | null | undefined) {
  if (!period) return ""
  if (period <= 4) return `Q${period}`
  const overtime = period - 4
  return overtime === 1 ? "OT" : `${overtime}OT`
}

// "2d 3h 14m" far out, "3h 14m 05s" on the day, "14m 05s" in the last hour
export function formatCountdown(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = String(total % 60).padStart(2, "0")
  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`
  return `${minutes}m ${seconds}s`
}
