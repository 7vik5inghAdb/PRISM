import { anthropic } from "@ai-sdk/anthropic";
import { generateObject, tool } from "ai";
import { z } from "zod";
import { MODELS } from "@/lib/ai/models";
import { SECONDARY_RESEARCH_SYSTEM } from "@/lib/ai/prompts/secondary-research";
import { webSearch } from "@/lib/ai/web-search";
import {
  SecondaryResearchSchema,
  type SecondaryResearch,
} from "@/lib/schemas/secondary-research";

export const secondaryResearch = tool({
  description:
    "Run a single web search on a topic and synthesize the results into a research note with citations and takeaways. Use for cultural context, competitive landscape, market signals, or any external fact-finding the PM asks for.",
  inputSchema: z.object({
    topic: z
      .string()
      .describe(
        "The research topic — keep concise (3-10 words). One topic per call.",
      ),
    query: z
      .string()
      .nullable()
      .describe(
        "Optional explicit web search query. If null, the topic is used as the query.",
      ),
  }),
  execute: async ({ topic, query }): Promise<SecondaryResearch> => {
    const searchQuery = query ?? topic;
    const results = await webSearch(searchQuery);
    const { object } = await generateObject({
      model: anthropic(MODELS.orchestrator),
      system: SECONDARY_RESEARCH_SYSTEM,
      prompt: `Topic: ${topic}\nSearch query: ${searchQuery}\n\nSearch results:\n${JSON.stringify(results, null, 2)}`,
      schema: SecondaryResearchSchema,
    });
    return object;
  },
});
