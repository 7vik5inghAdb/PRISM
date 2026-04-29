import { anthropic } from "@ai-sdk/anthropic";
import { generateObject, tool } from "ai";
import { z } from "zod";
import { MODELS } from "@/lib/ai/models";
import { AGGREGATOR_SYSTEM } from "@/lib/ai/prompts/aggregator";
import {
  AggregatorNarrativeSchema,
  type AggregatorResult,
  type ItemStats,
} from "@/lib/schemas/aggregator";
import { InstrumentSchema, type Instrument } from "@/lib/schemas/instrument";
import { PanelResultSchema, type PanelResult } from "@/lib/schemas/panel";

const round1 = (n: number) => Math.round(n * 10) / 10;
const normalize = (s: string) => s.trim().toLowerCase();

function summarizeLikert(answers: string[]) {
  const values = answers
    .map((a) => parseInt(a.match(/[1-5]/)?.[0] ?? "", 10))
    .filter((v) => !Number.isNaN(v) && v >= 1 && v <= 5);
  const mean = values.length
    ? round1(values.reduce((s, v) => s + v, 0) / values.length)
    : 0;
  const distribution = [1, 2, 3, 4, 5].map((value) => ({
    value,
    count: values.filter((x) => x === value).length,
  }));
  const distString = distribution
    .map((d) => `${d.value}:${d.count}`)
    .join(", ");
  return {
    mean,
    distribution,
    summary: `Mean ${mean} (n=${values.length}; ${distString})`,
  };
}

function summarizePreference(answers: string[], n: number) {
  const counts = new Map<string, { display: string; count: number }>();
  for (const a of answers) {
    const key = normalize(a);
    if (!key) continue;
    const existing = counts.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      counts.set(key, { display: a.trim(), count: 1 });
    }
  }
  const sorted = [...counts.values()].sort((a, b) => b.count - a.count);
  const top = sorted[0];
  return {
    counts: sorted.map(({ display, count }) => ({ choice: display, count })),
    topChoice: top?.display ?? null,
    summary: top
      ? `Top: "${top.display}" (${top.count}/${n})`
      : `n=${n}, no countable choice`,
  };
}

function summarizeRanking(answers: string[], n: number) {
  const positions = new Map<string, { display: string; ranks: number[] }>();
  for (const a of answers) {
    const tokens = a
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    tokens.forEach((token, idx) => {
      const key = normalize(token);
      const existing = positions.get(key);
      if (existing) {
        existing.ranks.push(idx + 1);
      } else {
        positions.set(key, { display: token, ranks: [idx + 1] });
      }
    });
  }
  const averages = [...positions.values()]
    .map(({ display, ranks }) => ({
      item: display,
      avgRank: round1(ranks.reduce((s, v) => s + v, 0) / ranks.length),
    }))
    .sort((a, b) => a.avgRank - b.avgRank);
  return {
    averages,
    summary: averages.length
      ? averages.map((a) => `${a.item} (${a.avgRank})`).join(" → ")
      : `n=${n}, no ranking parsed`,
  };
}

function computeItemStats(
  instrument: Instrument,
  panelResult: PanelResult,
): ItemStats[] {
  return instrument.items.map((item, idx) => {
    const answers = panelResult.respondents
      .flatMap((r) => r.answers)
      .filter((a) => a.itemIndex === idx)
      .map((a) => a.answer);
    const n = answers.length;

    if (item.responseType === "likert_5") {
      const { mean, distribution, summary } = summarizeLikert(answers);
      return {
        itemIndex: idx,
        question: item.question,
        responseType: item.responseType,
        n,
        summary,
        likertMean: mean,
        likertDistribution: distribution,
        preferenceCounts: null,
        topChoice: null,
        rankingAverages: null,
      };
    }
    if (item.responseType === "preference") {
      const { counts, topChoice, summary } = summarizePreference(answers, n);
      return {
        itemIndex: idx,
        question: item.question,
        responseType: item.responseType,
        n,
        summary,
        likertMean: null,
        likertDistribution: null,
        preferenceCounts: counts,
        topChoice,
        rankingAverages: null,
      };
    }
    if (item.responseType === "ranking") {
      const { averages, summary } = summarizeRanking(answers, n);
      return {
        itemIndex: idx,
        question: item.question,
        responseType: item.responseType,
        n,
        summary,
        likertMean: null,
        likertDistribution: null,
        preferenceCounts: null,
        topChoice: null,
        rankingAverages: averages,
      };
    }
    return {
      itemIndex: idx,
      question: item.question,
      responseType: item.responseType,
      n,
      summary: `n=${n} open responses`,
      likertMean: null,
      likertDistribution: null,
      preferenceCounts: null,
      topChoice: null,
      rankingAverages: null,
    };
  });
}

function buildNarrativePrompt(
  instrument: Instrument,
  panelResult: PanelResult,
  itemStats: ItemStats[],
): string {
  const blocks = itemStats.map((s) => {
    const header = `Q${s.itemIndex + 1} [${s.responseType}] ${s.question}\n  Stats: ${s.summary}`;
    if (s.responseType === "open_text") {
      const answerLines = panelResult.respondents
        .map((r) => {
          const a = r.answers.find((x) => x.itemIndex === s.itemIndex);
          return a ? `  ${r.id}: "${a.answer}"` : null;
        })
        .filter((line): line is string => line !== null)
        .join("\n");
      return `${header}\n  Answers:\n${answerLines}`;
    }
    return header;
  });
  return `Panel size: ${panelResult.panelSize}\n\nInstrument: ${instrument.title}\n${instrument.description}\n\n${blocks.join("\n\n")}`;
}

export const aggregator = tool({
  description:
    "Aggregate a panel's raw responses into deterministic per-item statistics plus LLM-narrated themes, disagreements, and a takeaway. Use after a panel has been simulated.",
  inputSchema: z.object({
    instrument: InstrumentSchema,
    panelResult: PanelResultSchema,
  }),
  execute: async ({ instrument, panelResult }): Promise<AggregatorResult> => {
    const itemStats = computeItemStats(instrument, panelResult);
    const prompt = buildNarrativePrompt(instrument, panelResult, itemStats);
    const { object: narrative } = await generateObject({
      model: anthropic(MODELS.orchestrator),
      system: AGGREGATOR_SYSTEM,
      prompt,
      schema: AggregatorNarrativeSchema,
    });
    return {
      panelSize: panelResult.panelSize,
      itemStats,
      ...narrative,
    };
  },
});
