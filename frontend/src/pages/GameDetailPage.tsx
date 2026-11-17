import { useParams } from "react-router"
import { PlaceholderPage } from "@/components/layout/PlaceholderPage"

export function GameDetailPage() {
  const { gameId } = useParams()
  return <PlaceholderPage title={`Game ${gameId}`} />
}
