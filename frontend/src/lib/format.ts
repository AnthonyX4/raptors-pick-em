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
