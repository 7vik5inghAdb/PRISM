import { anthropic } from "@ai-sdk/anthropic";
import { generateObject, tool } from "ai";
import { z } from "zod";
import { MODELS } from "@/lib/ai/models";
import { CHART_BUILDER_SYSTEM } from "@/lib/ai/prompts/chart-builder";
import { AggregatorResultSchema } from "@/lib/schemas/aggregator";
import { ChartSpecSchema, type ChartSpec } from "@/lib/schemas/chart";

export const chartBuilder = tool({
  description:
    "Build a chart from an aggregator result. Use after aggregation to visualize a specific item or finding.",
  inputSchema: z.object({
    aggregatorResult: AggregatorResultSchema,
    focus: z
      .string()
      .describe(
        "What to chart — e.g., 'Q3 likert distribution', 'Q1 preference shares', 'ranking averages from Q2'.",
      ),
  }),
  execute: async ({ aggregatorResult, focus }): Promise<ChartSpec> => {
    const { object } = await generateObject({
      model: anthropic(MODELS.orchestrator),
      system: CHART_BUILDER_SYSTEM,
      prompt: `Aggregator result:\n${JSON.stringify(aggregatorResult, null, 2)}\n\nFocus: ${focus}`,
      schema: ChartSpecSchema,
    });
    return object;
  },
});
