import { z } from "zod";

export const InstrumentItemSchema = z.object({
  question: z.string(),
  responseType: z.enum(["preference", "ranking", "likert_5", "open_text"]),
  rationale: z
    .string()
    .describe("Short reason this question maps to the research goal."),
});

export const InstrumentSchema = z.object({
  title: z
    .string()
    .describe("Short, plain-English study title — no jargon."),
  description: z
    .string()
    .describe(
      "2-3 sentences respondents see: what the study is about and what they will be asked.",
    ),
  items: z
    .array(InstrumentItemSchema)
    .describe(
      "5-8 ordered items. Include at least one preference or ranking item, 2-3 likert_5, and 2-3 open_text. No leading or double-barreled questions.",
    ),
});

export type Instrument = z.infer<typeof InstrumentSchema>;
export type InstrumentItem = z.infer<typeof InstrumentItemSchema>;
