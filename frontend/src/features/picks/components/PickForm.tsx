import { zodResolver } from "@hookform/resolvers/zod"
import { useMemo } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Form } from "@/components/ui/form"
import { FormError } from "@/features/auth/components/AuthCard"
import { errorMessage } from "@/features/auth/errors"
import type { GameDetail } from "@/features/games/api"
import type { Category, Pick, Player } from "../api"
import { useSavePicks } from "../hooks"
import { buildPickSchema, planSave, toFormValues, type PickValues } from "../schema"
import { PickField } from "./PickField"

interface PickFormProps {
  game: GameDetail
  categories: Category[]
  roster: Player[]
  saved: Pick[]
}

// the editable picks of an open game. seeded from the saved picks; a background refetch only touches the
// fields the person hasn't changed, so typing is never overwritten
export function PickForm({ game, categories, roster, saved }: PickFormProps) {
  const schema = useMemo(() => buildPickSchema(categories), [categories])
  const values = useMemo(() => toFormValues(categories, saved), [categories, saved])
  const form = useForm<PickValues>({ resolver: zodResolver(schema), values, resetOptions: { keepDirtyValues: true } })
  const save = useSavePicks(game.game_id)

  async function onSubmit(formValues: PickValues) {
    const steps = planSave(categories, formValues, saved)
    if (steps.length === 0) return
    try {
      await save.mutateAsync(steps)
      toast.success("Picks saved")
    } catch {
      // shown under the form: save.error. the picks that did go through are already reflected
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={(event) => {
          save.reset()
          return form.handleSubmit(onSubmit)(event)
        }}
        className="space-y-6 rounded-md border border-border bg-card p-8 max-md:p-5"
        noValidate
      >
        {categories.map((category) => (
          <PickField
            key={category.pick_category_id}
            category={category}
            control={form.control}
            teams={[game.away_team, game.home_team]}
            roster={roster}
          />
        ))}
        {save.isError && <FormError message={errorMessage(save.error)} />}
        <div className="flex items-center gap-4">
          <Button
            type="submit"
            size="lg"
            className="font-bold tracking-wide uppercase"
            disabled={!form.formState.isDirty || save.isPending}
          >
            {save.isPending ? "Saving…" : "Save picks"}
          </Button>
          <p className="text-sm text-muted-foreground">You can change your picks until tipoff.</p>
        </div>
      </form>
    </Form>
  )
}
