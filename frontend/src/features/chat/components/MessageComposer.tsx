import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { MESSAGE_MAX_LENGTH } from "@/lib/constants"
import { chatErrorMessage } from "../errors"

interface MessageComposerProps {
  onSubmit: (body: string) => Promise<unknown>
  submitLabel: string
  initial?: string
  placeholder?: string
  autoFocus?: boolean
  onCancel?: () => void
}

// the box a message is typed in, for a new message and for an edit. Enter sends, Shift+Enter is a new line.
// a failed send keeps the text and says why under the box (muted, room closed, edit window over)
export function MessageComposer({ onSubmit, submitLabel, initial = "", placeholder, autoFocus, onCancel }: MessageComposerProps) {
  const [text, setText] = useState(initial)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const body = text.trim()
  const tooLong = body.length > MESSAGE_MAX_LENGTH
  const canSend = body.length > 0 && !tooLong && !pending

  async function submit() {
    if (!canSend) return
    setPending(true)
    setError(null)
    try {
      await onSubmit(body)
      setText("")
    } catch (e) {
      setError(chatErrorMessage(e))
    } finally {
      setPending(false)
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        void submit()
      }}
      className="space-y-2"
    >
      <Textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          // not while an IME is composing: Enter there picks a character
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            void submit()
          }
          if (event.key === "Escape" && onCancel) onCancel()
        }}
        placeholder={placeholder}
        aria-label={placeholder ?? "Message"}
        autoFocus={autoFocus}
        rows={2}
        className="min-h-0 resize-none"
      />
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex items-center justify-between gap-3">
        <span className={tooLong ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
          {body.length}/{MESSAGE_MAX_LENGTH}
        </span>
        <div className="flex gap-2">
          {onCancel && (
            <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button type="submit" size="sm" className="font-bold tracking-wide uppercase" disabled={!canSend}>
            {pending ? "Sending…" : submitLabel}
          </Button>
        </div>
      </div>
    </form>
  )
}
