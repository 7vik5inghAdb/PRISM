"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  type Instrument,
  type InstrumentItem,
} from "@/lib/schemas/instrument";

const RESPONSE_TYPE_LABEL: Record<InstrumentItem["responseType"], string> = {
  preference: "Preference",
  ranking: "Ranking",
  likert_5: "Likert (5)",
  open_text: "Open text",
};

export function InstrumentCard({
  instrument,
  onRegenerate,
}: {
  instrument: Instrument;
  onRegenerate?: (brief: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [brief, setBrief] = useState("");

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">
            Instrument
          </div>
          <div className="text-base font-medium text-zinc-900">
            {instrument.title}
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

      <p className="mt-2 text-sm text-zinc-700">{instrument.description}</p>

      <ol className="mt-3 flex flex-col gap-3">
        {instrument.items.map((item, i) => (
          <li key={i} className="text-sm">
            <div className="flex items-baseline gap-2">
              <span className="shrink-0 text-zinc-500">{i + 1}.</span>
              <span className="flex-1 text-zinc-900">{item.question}</span>
              <span className="shrink-0 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-600">
                {RESPONSE_TYPE_LABEL[item.responseType]}
              </span>
            </div>
            <div className="ml-5 mt-0.5 text-xs text-zinc-500">
              {item.rationale}
            </div>
          </li>
        ))}
      </ol>

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
            Regenerate with new goal or notes
          </label>
          <Textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={2}
            className="resize-none text-sm"
            placeholder="Describe the updated study goal or notes…"
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

export function InstrumentCardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 text-xs text-zinc-500 shadow-sm">
      Designing instrument…
    </div>
  );
}
