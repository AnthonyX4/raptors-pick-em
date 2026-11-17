import { describe, expect, it } from "vitest"
import type { Category, Pick } from "./api"
import { buildPickSchema, planSave, toFormValues, type PickValues } from "./schema"

const category = (id: number, kind: Category["kind"], required = false): Category => ({
  pick_category_id: id,
  key: `k${id}`,
  kind,
  stat: kind === "stat_leader" ? "points" : null,
  name: kind === "winner" ? "Winner" : `Category ${id}`,
  points: 1,
  is_required: required,
  is_active: true,
  sort_order: id,
})

const winner = category(1, "winner", true)
const margin = category(2, "margin")
const scorer = category(3, "stat_leader")
const categories = [winner, margin, scorer]

const team = { team_id: 10, tricode: "TOR", city: "Toronto", nickname: "Raptors", full_name: "Toronto Raptors" }
const player = { player_id: 7, full_name: "A Player", first_name: "A", last_name: "Player", jersey_number: null, position: null, team }

// a saved pick: answers go in the field the category's kind asks for
function saved(cat: Category, pickId: number, answer: { team?: number; margin?: number; player?: number }): Pick {
  return {
    pick_id: pickId,
    game_id: "g1",
    category: cat,
    team: answer.team ? { ...team, team_id: answer.team } : null,
    player: answer.player ? { ...player, player_id: answer.player } : null,
    margin: answer.margin ?? null,
    points_awarded: null,
    created_at: "2026-11-17T00:00:00Z",
    updated_at: "2026-11-17T00:00:00Z",
  }
}

const values = (v: Partial<Record<number, string>>): PickValues =>
  Object.fromEntries(categories.map((c) => [String(c.pick_category_id), v[c.pick_category_id] ?? ""]))

describe("toFormValues", () => {
  it("turns saved picks into one string per category", () => {
    const form = toFormValues(categories, [saved(winner, 100, { team: 10 }), saved(margin, 101, { margin: 8 })])
    expect(form).toEqual({ "1": "10", "2": "8", "3": "" })
  })

  it("ignores picks in categories that aren't on the form", () => {
    expect(toFormValues([winner], [saved(scorer, 102, { player: 7 })])).toEqual({ "1": "" })
  })
})

describe("planSave", () => {
  it("creates the winner before the bonus picks", () => {
    const steps = planSave(categories, values({ 1: "10", 2: "5", 3: "7" }), [])
    expect(steps.map((s) => [s.type, s.categoryId])).toEqual([
      ["create", 1],
      ["create", 2],
      ["create", 3],
    ])
    expect(steps[0]).toMatchObject({ body: { team_id: 10 } })
    expect(steps[1]).toMatchObject({ body: { margin: 5 } })
    expect(steps[2]).toMatchObject({ body: { player_id: 7 } })
  })

  it("sends nothing when nothing changed", () => {
    const picks = [saved(winner, 100, { team: 10 }), saved(margin, 101, { margin: 8 })]
    expect(planSave(categories, toFormValues(categories, picks), picks)).toEqual([])
  })

  it("updates only what changed", () => {
    const picks = [saved(winner, 100, { team: 10 }), saved(margin, 101, { margin: 8 })]
    const steps = planSave(categories, values({ 1: "10", 2: "12" }), picks)
    expect(steps).toEqual([
      { type: "update", pickId: 101, categoryId: 2, categoryName: "Category 2", body: { margin: 12 } },
    ])
  })

  it("withdraws bonus picks after writing and the winner last", () => {
    const picks = [saved(winner, 100, { team: 10 }), saved(margin, 101, { margin: 8 }), saved(scorer, 102, { player: 7 })]
    // changing the winner while withdrawing a bonus pick: update first, delete after
    const change = planSave(categories, values({ 1: "11", 3: "7" }), picks)
    expect(change.map((s) => [s.type, s.categoryId])).toEqual([
      ["update", 1],
      ["delete", 2],
    ])
    // withdrawing everything: bonus picks go before the winner or the server refuses it
    const all = planSave(categories, values({}), picks)
    expect(all.map((s) => [s.type, s.categoryId])).toEqual([
      ["delete", 2],
      ["delete", 3],
      ["delete", 1],
    ])
  })

  it("treats a padded number as the same answer", () => {
    const picks = [saved(winner, 100, { team: 10 }), saved(margin, 101, { margin: 8 })]
    expect(planSave(categories, values({ 1: "10", 2: " 8 " }), picks)).toEqual([])
  })

  it("leaves a pick in an inactive category alone", () => {
    const stale = saved(category(9, "margin"), 109, { margin: 3 })
    expect(planSave(categories, values({ 1: "10" }), [saved(winner, 100, { team: 10 }), stale])).toEqual([])
  })
})

describe("buildPickSchema", () => {
  const schema = buildPickSchema(categories)
  const messages = (v: PickValues) => {
    const result = schema.safeParse(v)
    return result.success ? [] : result.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`)
  }

  it("accepts a winner alone, an empty form and a full one", () => {
    expect(messages(values({ 1: "10" }))).toEqual([])
    expect(messages(values({}))).toEqual([])
    expect(messages(values({ 1: "10", 2: "99", 3: "7" }))).toEqual([])
  })

  it("wants a winner before any bonus pick", () => {
    expect(messages(values({ 3: "7" }))).toEqual(["1: Make your winner pick before the others"])
  })

  it("keeps a margin to a whole number from 1 to 99", () => {
    for (const bad of ["0", "100", "-3", "4.5", "abc"]) {
      expect(messages(values({ 1: "10", 2: bad }))).toEqual(["2: A whole number from 1 to 99"])
    }
  })
})
