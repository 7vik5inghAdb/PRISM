import { z } from "zod";

export const ChartDataPointSchema = z.object({
  label: z.string(),
  value: z.number(),
});

export const ChartSpecSchema = z.object({
  title: z.string().describe("Plain English chart title."),
  description: z
    .string()
    .nullable()
    .describe("One sentence explaining what the chart shows."),
  chartType: z
    .enum(["bar", "horizontal_bar"])
    .describe(
      "bar: items along x, value along y (good for likert distributions, preference counts). horizontal_bar: items along y, value along x (good for ranking averages or many categories).",
    ),
  data: z
    .array(ChartDataPointSchema)
    .describe(
      "Data points pulled from the aggregator result. Don't invent values.",
    ),
  xAxisLabel: z.string().nullable(),
  yAxisLabel: z.string().nullable(),
});

export type ChartDataPoint = z.infer<typeof ChartDataPointSchema>;
export type ChartSpec = z.infer<typeof ChartSpecSchema>;
