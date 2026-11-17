import { z } from "zod"

// an admin's mute: the same limits as the backend's MuteCreate (1 hour to 30 days, a reason up to 200).
// the hours are typed into a field, so they arrive as text
export const muteSchema = z.object({
  hours: z
    .string()
    .regex(/^\d+$/, "A whole number of hours")
    .refine((value) => Number(value) >= 1 && Number(value) <= 720, "From 1 to 720 hours (30 days)"),
  reason: z.string().max(200, "At most 200 characters"),
})

export type MuteValues = z.infer<typeof muteSchema>
