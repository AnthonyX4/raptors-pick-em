import { useEffect } from "react"

const SITE = "Raptors Pick'em"

// the tab title (and what a screen reader says on arriving) for the page being shown. without a title
// it is just the site name; it goes back to that when the page unmounts
export function useDocumentTitle(title?: string | null) {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE}` : SITE
    return () => {
      document.title = SITE
    }
  }, [title])
}
