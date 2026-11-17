import { z } from "zod"
import type { Category, Pick } from "./api"

// the form holds one string per category, keyed by the category's id: "" is no pick, otherwise a team id
// (winner), a number of points (margin) or a player id (stat leader). the form is built from the category
// list, so a category an admin adds becomes a field with no code change
export type PickValues = Record<string, string>

export const fieldName = (category: Category) => String(category.pick_category_id)

type Answer = { team_id: number } | { margin: number } | { player_id: number }

// a pick body fills in exactly the one answer field its category's kind asks for: anything else is a 400
function bodyFor(category: Category, value: string): Answer {
  const n = Number(value)
  switch (category.kind) {
    case "winner":
      return { team_id: n }
    case "margin":
      return { margin: n }
    case "stat_leader":
      return { player_id: n }
  }
}

// the saved answer as a form value, the same shape the form edits
function answerOf(category: Category, pick: Pick): string {
  switch (category.kind) {
    case "winner":
      return pick.team ? String(pick.team.team_id) : ""
    case "margin":
      return pick.margin === null ? "" : String(pick.margin)
    case "stat_leader":
      return pick.player ? String(pick.player.player_id) : ""
  }
}

export function toFormValues(categories: Category[], saved: Pick[]): PickValues {
  const values: PickValues = {}
  for (const category of categories) {
    const pick = saved.find((p) => p.category.pick_category_id === category.pick_category_id)
    values[fieldName(category)] = pick ? answerOf(category, pick) : ""
  }
  return values
}

const blank = (value: string | undefined) => !value || value.trim() === ""

// mirrors the backend's rules so mistakes show before a round trip; the server stays the authority
export function buildPickSchema(categories: Category[]) {
  return z.record(z.string(), z.string()).superRefine((values, ctx) => {
    for (const category of categories) {
      const value = values[fieldName(category)]
      if (category.kind === "margin" && !blank(value)) {
        const n = Number(value)
        if (!/^\d+$/.test(value.trim()) || n < 1 || n > 99) {
          ctx.addIssue({ code: "custom", path: [fieldName(category)], message: "A whole number from 1 to 99" })
        }
      }
    }

    // bonus picks only count alongside the required ones, and the server refuses them without
    const hasBonus = categories.some((c) => !c.is_required && !blank(values[fieldName(c)]))
    if (hasBonus) {
      for (const category of categories) {
        if (category.is_required && blank(values[fieldName(category)])) {
          ctx.addIssue({
            code: "custom",
            path: [fieldName(category)],
            message: `Make your ${category.name.toLowerCase()} pick before the others`,
          })
        }
      }
    }
  })
}

export type SaveStep =
  | { type: "create"; categoryId: number; categoryName: string; body: Answer }
  | { type: "update"; pickId: number; categoryId: number; categoryName: string; body: Answer }
  | { type: "delete"; pickId: number; categoryId: number; categoryName: string }

// what has to be sent to turn the saved picks into the form's, one request per changed category, in the
// order the backend's rules allow: the required pick first (bonus picks are refused without it), then the
// bonus picks, then withdrawals of bonus picks, and a required pick last (it can't go while bonus picks
// stand). unchanged picks are skipped, and picks in categories that are no longer active are left alone
export function planSave(categories: Category[], values: PickValues, saved: Pick[]): SaveStep[] {
  const required = categories.filter((c) => c.is_required)
  const bonus = categories.filter((c) => !c.is_required)

  const savedFor = (category: Category) =>
    saved.find((p) => p.category.pick_category_id === category.pick_category_id)

  const writes = (list: Category[]): SaveStep[] =>
    list.flatMap((category): SaveStep[] => {
      const value = (values[fieldName(category)] ?? "").trim()
      if (blank(value)) return []
      const pick = savedFor(category)
      const base = { categoryId: category.pick_category_id, categoryName: category.name }
      if (!pick) return [{ type: "create", ...base, body: bodyFor(category, value) }]
      if (answerOf(category, pick) === value) return []
      return [{ type: "update", pickId: pick.pick_id, ...base, body: bodyFor(category, value) }]
    })

  const deletes = (list: Category[]): SaveStep[] =>
    list.flatMap((category): SaveStep[] => {
      const pick = savedFor(category)
      if (!pick || !blank(values[fieldName(category)])) return []
      return [{ type: "delete", pickId: pick.pick_id, categoryId: category.pick_category_id, categoryName: category.name }]
    })

  return [...writes(required), ...writes(bonus), ...deletes(bonus), ...deletes(required)]
}
