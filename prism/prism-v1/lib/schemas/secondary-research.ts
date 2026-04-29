import { z } from "zod";

export const CitationSchema = z.object({
  title: z.string(),
  url: z.string(),
  snippet: z.string(),
});

export const SecondaryResearchSchema = z.object({
  topic: z.string(),
  summary: z
    .string()
    .describe(
      "2-4 paragraph synthesis of what the search results say about the topic.",
    ),
  citations: z
    .array(CitationSchema)
    .describe(
      "The supporting search results referenced in the summary. Use the actual title/URL/snippet from search; don't fabricate.",
    ),
  takeaways: z
    .array(z.string())
    .describe("3-5 bullet takeaways the PM can act on."),
});

export type Citation = z.infer<typeof CitationSchema>;
export type SecondaryResearch = z.infer<typeof SecondaryResearchSchema>;
