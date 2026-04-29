import { anthropic } from "@ai-sdk/anthropic";
import { generateObject, tool } from "ai";
import { z } from "zod";
import { MODELS } from "@/lib/ai/models";
import { INSTRUMENT_DESIGNER_SYSTEM } from "@/lib/ai/prompts/instrument-designer";
import { InstrumentSchema, type Instrument } from "@/lib/schemas/instrument";

export const instrumentDesigner = tool({
  description:
    "Design a research instrument (5-8 items mixing preference/ranking/likert_5/open_text) for a research goal. Use after the PM has stated a study goal; pass any persona or target context inline as notes.",
  inputSchema: z.object({
    goal: z
      .string()
      .describe(
        "The PM's research goal, hypothesis, or what they want to learn from respondents.",
      ),
    notes: z
      .string()
      .optional()
      .describe(
        "Optional context — persona summary, target segment, constraints, or stimulus respondents will see.",
      ),
  }),
  execute: async ({ goal, notes }): Promise<Instrument> => {
    const prompt = notes
      ? `Goal: ${goal}\n\nNotes: ${notes}`
      : `Goal: ${goal}`;
    const { object } = await generateObject({
      model: anthropic(MODELS.orchestrator),
      system: INSTRUMENT_DESIGNER_SYSTEM,
      prompt,
      schema: InstrumentSchema,
    });
    return object;
  },
});
