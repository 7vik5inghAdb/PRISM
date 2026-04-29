import { anthropic } from "@ai-sdk/anthropic";
import { generateObject, tool } from "ai";
import { z } from "zod";
import { MODELS } from "@/lib/ai/models";
import { PERSONA_GENERATOR_SYSTEM } from "@/lib/ai/prompts/persona-generator";
import { PersonaSchema, type Persona } from "@/lib/schemas/persona";

export const personaGenerator = tool({
  description:
    "Generate one synthetic UX research persona from a brief. Use when the PM has described a study target or feature and wants a persona to anchor research planning.",
  inputSchema: z.object({
    brief: z
      .string()
      .describe(
        "The PM's description of the persona target, study goal, or feature being researched.",
      ),
  }),
  execute: async ({ brief }): Promise<Persona> => {
    const { object } = await generateObject({
      model: anthropic(MODELS.orchestrator),
      system: PERSONA_GENERATOR_SYSTEM,
      prompt: `Brief: ${brief}`,
      schema: PersonaSchema,
    });
    return object;
  },
});
