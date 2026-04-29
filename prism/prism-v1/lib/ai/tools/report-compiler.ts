import { anthropic } from "@ai-sdk/anthropic";
import { generateObject, tool } from "ai";
import { z } from "zod";
import { MODELS } from "@/lib/ai/models";
import { REPORT_COMPILER_SYSTEM } from "@/lib/ai/prompts/report-compiler";
import { AggregatorResultSchema } from "@/lib/schemas/aggregator";
import { ChartSpecSchema } from "@/lib/schemas/chart";
import { InstrumentSchema } from "@/lib/schemas/instrument";
import { PanelResultSchema } from "@/lib/schemas/panel";
import { PersonaSchema } from "@/lib/schemas/persona";
import { ReportSchema, type Report } from "@/lib/schemas/report";
import { SecondaryResearchSchema } from "@/lib/schemas/secondary-research";

export const reportCompiler = tool({
  description:
    "Compile a final research report from whatever cards exist (persona, instrument, panel result, aggregator, charts, secondary research). Use when the PM asks for a written report or summary deliverable.",
  inputSchema: z.object({
    hypothesis: z
      .string()
      .describe(
        "The PM's research hypothesis or question this study addresses.",
      ),
    persona: PersonaSchema.nullable(),
    instrument: InstrumentSchema.nullable(),
    panelResult: PanelResultSchema.nullable(),
    aggregatorResult: AggregatorResultSchema.nullable(),
    charts: z.array(ChartSpecSchema).nullable(),
    secondaryResearch: z.array(SecondaryResearchSchema).nullable(),
  }),
  execute: async (input): Promise<Report> => {
    const { object } = await generateObject({
      model: anthropic(MODELS.orchestrator),
      system: REPORT_COMPILER_SYSTEM,
      prompt: `Today's date: ${new Date().toISOString().slice(0, 10)}\n\nInputs:\n${JSON.stringify(input, null, 2)}`,
      schema: ReportSchema,
    });
    return object;
  },
});
