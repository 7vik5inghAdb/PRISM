import { z } from "zod";

export const LikertDistributionSchema = z.object({
  value: z.number(),
  count: z.number(),
});

export const PreferenceCountSchema = z.object({
  choice: z.string(),
  count: z.number(),
});

export const RankingAverageSchema = z.object({
  item: z.string(),
  avgRank: z.number(),
});

export const ItemStatsSchema = z.object({
  itemIndex: z.number(),
  question: z.string(),
  responseType: z.enum(["preference", "ranking", "likert_5", "open_text"]),
  n: z.number(),
  summary: z.string(),
  likertMean: z.number().nullable(),
  likertDistribution: z.array(LikertDistributionSchema).nullable(),
  preferenceCounts: z.array(PreferenceCountSchema).nullable(),
  topChoice: z.string().nullable(),
  rankingAverages: z.array(RankingAverageSchema).nullable(),
});

export const AggregatorNarrativeSchema = z.object({
  topThemes: z
    .array(z.string())
    .describe("3-5 highest-signal themes across the panel."),
  notableDisagreements: z
    .array(z.string())
    .describe(
      "Places where respondents diverge. Cite specifics (e.g., 'R02 vs R04 on Q3'). Empty if everyone agrees.",
    ),
  takeaway: z
    .string()
    .describe(
      "2-4 sentence verdict on what the panel reveals. Hedge if signal is marginal or convergence is structural.",
    ),
});

export const AggregatorResultSchema = z.object({
  panelSize: z.number(),
  itemStats: z.array(ItemStatsSchema),
  topThemes: z.array(z.string()),
  notableDisagreements: z.array(z.string()),
  takeaway: z.string(),
});

export type ItemStats = z.infer<typeof ItemStatsSchema>;
export type AggregatorNarrative = z.infer<typeof AggregatorNarrativeSchema>;
export type AggregatorResult = z.infer<typeof AggregatorResultSchema>;
