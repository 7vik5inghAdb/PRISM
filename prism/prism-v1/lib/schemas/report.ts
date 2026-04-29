import { z } from "zod";

export const ReportSectionSchema = z.object({
  heading: z.string(),
  body: z
    .string()
    .describe(
      "Plain text or simple markdown (paragraphs, **bold**, lists). No images, tables, or links.",
    ),
});

export const ReportSchema = z.object({
  title: z.string().describe("Plain-English report title."),
  date: z.string().describe("ISO date the report was compiled."),
  hypothesis: z
    .string()
    .nullable()
    .describe(
      "The hypothesis or research question this study addressed, restated.",
    ),
  executiveSummary: z
    .string()
    .describe("3-5 sentences, paste-into-Slack grade."),
  sections: z
    .array(ReportSectionSchema)
    .describe(
      "4-8 sections backed by available inputs (persona, instrument, panel, aggregator, charts, secondary). Skip sections without source data.",
    ),
  recommendations: z
    .array(z.string())
    .describe("3-6 prioritized, concrete actions. No vague 'improve X'."),
});

export type ReportSection = z.infer<typeof ReportSectionSchema>;
export type Report = z.infer<typeof ReportSchema>;
