import { Heart, MoreHorizontal } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { UserPrivate } from "@/features/auth/api"
import { formatDateTime, formatTime } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { ChatMessage } from "../api"
import type { ChatActions } from "../hooks"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { MessageComposer } from "./MessageComposer"
import { MuteDialog } from "./MuteDialog"

interface MessageItemProps {
  message: ChatMessage
  me: UserPrivate | null
  nowMs: number // ticks every few seconds, so the Edit entry goes when the window ends
  roomOpen: boolean
  actions: ChatActions
}

export function MessageItem({ message, me, nowMs, roomOpen, actions }: MessageItemProps) {
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [muting, setMuting] = useState(false)

  const { author } = message
  const isOwn = !!me && author?.user_id === me.user_id
  const isAdmin = !!me?.is_admin
  // editable_until comes from the api: the 5 minute rule lives there, this only reads it
  const canEdit = isOwn && nowMs < new Date(message.editable_until).getTime()
  const canDelete = isOwn || isAdmin
  const canMute = isAdmin && !!author && !isOwn
  const hasMenu = canEdit || canDelete || canMute

  // liking needs an open room, taking a like back doesn't
  const canLike = !!me && (roomOpen || message.liked_by_me)

  return (
    <li className="group flex gap-3 px-4 py-2 hover:bg-white/[0.03]">
      <Avatar className="mt-0.5 size-8 shrink-0">
        {author && <AvatarImage src={author.image_path} alt="" />}
        <AvatarFallback>{author ? author.username.slice(0, 1).toUpperCase() : "?"}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          {author ? (
            <Link to={`/users/${author.user_id}`} className="truncate text-sm font-bold hover:underline">
              {author.username}
            </Link>
          ) : (
            <span className="text-sm font-bold text-muted-foreground italic">[deleted]</span>
          )}
          <time dateTime={message.created_at} title={formatDateTime(message.created_at)} className="shrink-0 text-xs text-muted-foreground">
            {formatTime(message.created_at)}
          </time>
          {message.edited_at && <span className="text-xs text-muted-foreground">(edited)</span>}
        </div>

        {editing ? (
          <div className="mt-1">
            <MessageComposer
              initial={message.body}
              submitLabel="Save"
              autoFocus
              onCancel={() => setEditing(false)}
              onSubmit={async (body) => {
                await actions.edit.mutateAsync({ messageId: message.message_id, body })
                setEditing(false)
              }}
            />
          </div>
        ) : (
          // text, never html: a message is rendered as typed, with its line breaks
          <p className="text-sm break-words whitespace-pre-wrap">{message.body}</p>
        )}
      </div>

      <div className="flex shrink-0 items-start gap-1">
        <button
          type="button"
          aria-pressed={message.liked_by_me}
          aria-label={message.liked_by_me ? "Unlike" : "Like"}
          disabled={!canLike || actions.like.isPending}
          onClick={() => actions.like.mutate({ messageId: message.message_id, liked: !message.liked_by_me })}
          className={cn(
            "flex items-center gap-1 rounded-md px-1.5 py-1 text-xs transition-colors enabled:hover:bg-white/10 disabled:cursor-default",
            message.liked_by_me ? "text-primary" : "text-muted-foreground",
            message.like_count === 0 && !message.liked_by_me && "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
          )}
        >
          <Heart className={cn("size-3.5", message.liked_by_me && "fill-current")} />
          {message.like_count > 0 && <span>{message.like_count}</span>}
        </button>
        {hasMenu && (
          <DropdownMenu>
            <DropdownMenuTrigger
              aria-label="Message actions"
              className="rounded-md p-1 text-muted-foreground opacity-0 transition-opacity outline-none group-focus-within:opacity-100 group-hover:opacity-100 hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-ring data-[state=open]:opacity-100"
            >
              <MoreHorizontal className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {canEdit && <DropdownMenuItem onSelect={() => setEditing(true)}>Edit</DropdownMenuItem>}
              {canDelete && (
                <DropdownMenuItem onSelect={() => setConfirmingDelete(true)}>
                  {isAdmin && !isOwn ? "Delete (admin)" : "Delete"}
                </DropdownMenuItem>
              )}
              {canMute && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => setMuting(true)}>Mute author</DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        title="Delete this message?"
        description={isOwn ? "It's removed for everyone, and its likes go with it." : "Removed as a moderator, for everyone."}
        confirmLabel="Delete"
        pending={actions.remove.isPending}
        onConfirm={() =>
          actions.remove.mutate(
            { messageId: message.message_id, asAdmin: isAdmin && !isOwn },
            { onSettled: () => setConfirmingDelete(false) },
          )
        }
      />
      {canMute && author && <MuteDialog user={author} open={muting} onOpenChange={setMuting} mute={actions.mute} />}
    </li>
  )
}
