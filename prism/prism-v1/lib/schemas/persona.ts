import { z } from "zod";

export const PersonaSchema = z.object({
  name: z.string(),
  demographics: z.object({
    ageRange: z.string().describe("e.g. '28-34'"),
    gender: z.string(),
    location: z.string().describe("city or city + country"),
    occupation: z.string().describe("specific role, not a category"),
  }),
  characteristics: z
    .array(z.string())
    .describe("4-6 specific traits, behaviors, or attitudes — not generic adjectives"),
  painPoints: z
    .array(z.string())
    .describe("3-5 frustrations or unmet needs relevant to the brief"),
  goals: z
    .array(z.string())
    .describe("2-4 motivations or outcomes the persona is trying to reach"),
});

export type Persona = z.infer<typeof PersonaSchema>;
