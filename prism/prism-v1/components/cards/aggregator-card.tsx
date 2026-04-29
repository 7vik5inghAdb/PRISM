"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  type AggregatorResult,
  type ItemStats,
} from "@/lib/schemas/aggregator";

const RESPONSE_TYPE_LABEL: Record<ItemStats["responseType"], string> = {
  preference: "Preference",
  ranking: "Ranking",
  likert_5: "Likert (5)",
  open_text: "Open text",
};

export function AggregatorCard({
  result,
  onRegenerate,
}: {
  result: AggregatorResult;
  onRegenerate?: (brief: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [brief, setBrief] = useState("");

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">
            Aggregator
          </div>
          <div className="text-base font-medium text-zinc-900">
            {result.panelSize} respondents
          </div>
        </div>
        {onRegenerate && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setEditing((e) => !e);
              setBrief("");
            }}
          >
            {editing ? "Cancel" : "Edit"}
          </Button>
        )}
      </div>

      <p className="mt-2 rounded-md bg-zinc-50 p-3 text-sm text-zinc-800">
        {result.takeaway}
      </p>

      <div className="mt-3 flex flex-col gap-2">
        {result.itemStats.map((s) => (
          <div key={s.itemIndex} className="text-sm">
            <div className="flex items-baseline gap-2">
              <span className="shrink-0 text-zinc-500">{s.itemIndex + 1}.</span>
              <span className="flex-1 text-zinc-900">{s.question}</span>
              <span className="shrink-0 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-600">
                {RESPONSE_TYPE_LABEL[s.responseType]}
              </span>
            </div>
            <div className="ml-5 mt-0.5 text-xs text-zinc-600">{s.summary}</div>
          </div>
        ))}
      </div>

      {result.topThemes.length > 0 && (
        <Section title="Themes" items={result.topThemes} />
      )}
      {result.notableDisagreements.length > 0 && (
        <Section title="Disagreements" items={result.notableDisagreements} />
      )}

      {editing && onRegenerate && (
        <form
          className="mt-4 flex flex-col gap-2 border-t border-zinc-200 pt-3"
          onSubmit={(e) => {
            e.preventDefault();
            const value = brief.trim();
            if (!value) return;
            onRegenerate(value);
            setEditing(false);
            setBrief("");
          }}
        >
          <label className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Re-aggregate with new emphasis
          </label>
          <Textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={2}
            className="resize-none text-sm"
            placeholder="Describe what to focus on…"
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={!brief.trim()}>
              Regenerate
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

export function AggregatorCardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 text-xs text-zinc-500 shadow-sm">
      Aggregating panel…
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-3">
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
        {title}
      </div>
      <ul className="mt-1 list-inside list-disc text-sm text-zinc-800">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}
