import { ArrowRight } from "lucide-react"
import { Link } from "react-router"
import { cn } from "@/lib/utils"

interface MediaCardProps {
  to: string
  title: string
  cta?: string // shown bottom right once the card is hovered
  image?: string // without one the card is red with the logo as a watermark
  className?: string
}

// a big tappable tile: condensed uppercase title over a darkened background. the dark layer keeps the
// title readable on any image and deepens on hover
export function MediaCard({ to, title, cta, image, className }: MediaCardProps) {
  return (
    <Link
      to={to}
      className={cn(
        "group relative block aspect-[1.4] overflow-hidden rounded-md border border-border bg-card shadow-lg",
        className,
      )}
    >
      {image ? (
        <img src={image} alt="" className="absolute inset-0 size-full object-cover" />
      ) : (
        <>
          <div className="absolute inset-0 bg-linear-to-br from-[#6b1014] to-[#2a0709]" />
          <img
            src="/raptors-logo.svg"
            alt=""
            className="absolute -bottom-6 -left-6 size-48 opacity-25"
          />
        </>
      )}
      <div className="absolute inset-0 bg-black/25 transition-colors duration-300 group-hover:bg-black/60" />
      <h3 className="absolute inset-0 flex items-center justify-center px-6 text-center font-display text-4xl leading-none font-bold tracking-wide uppercase">
        {title}
      </h3>
      {cta && (
        <span className="absolute right-5 bottom-4 flex items-center gap-2 font-display text-lg font-bold tracking-wide uppercase opacity-0 transition-opacity duration-300 group-hover:opacity-100">
          {cta}
          <ArrowRight className="size-4" />
        </span>
      )}
    </Link>
  )
}
