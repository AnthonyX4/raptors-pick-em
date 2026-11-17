import type { Control } from "react-hook-form"
import { Button } from "@/components/ui/button"
import { FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Team } from "@/features/games/api"
import type { Category, Player } from "../api"
import { fieldName, type PickValues } from "../schema"

interface PickFieldProps {
  category: Category
  control: Control<PickValues>
  teams: Team[] // the game's two teams, for a winner pick
  roster: Player[] // for a stat leader pick
}

// one field of the form, chosen by the category's kind
export function PickField({ category, control, teams, roster }: PickFieldProps) {
  return (
    <FormField
      control={control}
      name={fieldName(category)}
      render={({ field }) => (
        <FormItem>
          <div className="flex items-center justify-between gap-3">
            <FormLabel className="text-base">
              {category.name}
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                {category.points} {category.points === 1 ? "pt" : "pts"}
                {category.is_required ? " · required" : ""}
              </span>
            </FormLabel>
            {field.value && (
              <Button type="button" variant="ghost" size="xs" onClick={() => field.onChange("")}>
                Clear<span className="sr-only"> {category.name}</span>
              </Button>
            )}
          </div>

          {category.kind === "winner" && (
            <FormControl>
              <RadioGroup value={field.value} onValueChange={field.onChange} className="grid-cols-2 max-md:grid-cols-1">
                {teams.map((team) => (
                  <label
                    key={team.team_id}
                    className="flex cursor-pointer items-center gap-3 rounded-md border border-border px-4 py-3 transition-colors hover:border-white/40 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/10"
                  >
                    <RadioGroupItem value={String(team.team_id)} />
                    <span className="font-display text-xl font-bold tracking-wide uppercase">{team.full_name}</span>
                  </label>
                ))}
              </RadioGroup>
            </FormControl>
          )}

          {category.kind === "margin" && (
            <>
              <FormControl>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={99}
                  placeholder="Points"
                  className="max-w-40"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                The winning margin, whoever wins. It only scores if your winner pick is right too.
              </FormDescription>
            </>
          )}

          {category.kind === "stat_leader" && (
            <Select value={field.value} onValueChange={field.onChange}>
              <FormControl>
                <SelectTrigger className="w-full max-w-72">
                  <SelectValue placeholder="Choose a player" />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                {roster.map((player) => (
                  <SelectItem key={player.player_id} value={String(player.player_id)}>
                    {player.full_name}
                    {player.position && <span className="text-muted-foreground"> · {player.position}</span>}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <FormMessage />
        </FormItem>
      )}
    />
  )
}
