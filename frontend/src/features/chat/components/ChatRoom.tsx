import { Link, useLocation } from "react-router"
import { Button } from "@/components/ui/button"
import { ErrorState, Loading } from "@/components/states"
import { useAuth } from "@/features/auth/useAuth"
import { useNow } from "@/hooks/useNow"
import { formatDateTime } from "@/lib/format"
import { useChatActions, useGameChat } from "../hooks"
import { MessageComposer } from "./MessageComposer"
import { MessageList } from "./MessageList"

function LoginPrompt() {
  const location = useLocation()
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground">Log in to join the chat.</p>
      <Button asChild size="sm" className="font-bold tracking-wide uppercase">
        <Link to="/login" state={{ from: location }}>Log in</Link>
      </Button>
    </div>
  )
}

// the game's chat room. whether it is open comes from the api (room_open); the clock is only used to word
// the closed state: before opens_at it says when, otherwise it's over
export function ChatRoom({ gameId }: { gameId: string }) {
  const { user, isLoading: authLoading } = useAuth()
  const { chat, isPending, isError, refetch, isFetching, loadOlder, loadingOlder } = useGameChat(gameId)
  const actions = useChatActions(gameId)
  const nowMs = useNow(15_000)

  let body: React.ReactNode
  let footer: React.ReactNode = null
  if (isPending) {
    body = <Loading what="the chat" className="m-4 h-40" />
  } else if (isError || !chat) {
    body = <ErrorState what="the chat" onRetry={() => void refetch()} retrying={isFetching} className="p-4" />
  } else {
    body = (
      <MessageList
        messages={chat.messages}
        hasOlder={chat.hasOlder}
        loadingOlder={loadingOlder}
        onLoadOlder={() => void loadOlder()}
        me={user ?? null}
        nowMs={nowMs}
        roomOpen={chat.roomOpen}
        actions={actions}
        empty={chat.roomOpen ? "No messages yet. Say something." : "No messages."}
      />
    )
    if (!chat.roomOpen) {
      footer = (
        <p className="text-sm text-muted-foreground">
          {nowMs < new Date(chat.opensAt).getTime() ? `Chat opens ${formatDateTime(chat.opensAt)}` : "Chat closed"}
        </p>
      )
    } else if (!authLoading) {
      footer = user ? (
        <MessageComposer
          submitLabel="Send"
          placeholder="Say something"
          onSubmit={(text) => actions.send.mutateAsync(text)}
        />
      ) : (
        <LoginPrompt />
      )
    }
  }

  return (
    <section
      aria-label="Game chat"
      className="flex h-[calc(100vh-7rem)] min-h-96 flex-col overflow-hidden rounded-md border border-border bg-card max-lg:h-[36rem]"
    >
      <h2 className="border-b border-border px-4 py-3 font-display text-2xl leading-none font-bold tracking-wide uppercase">
        Chat
      </h2>
      {body}
      {footer && <div className="border-t border-border p-4">{footer}</div>}
    </section>
  )
}
