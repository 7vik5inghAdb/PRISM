"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { type PanelResult } from "@/lib/schemas/panel";

export function PanelResultCard({
  result,
  onRegenerate,
}: {
  result: PanelResult;
  onRegenerate?: (brief: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [brief, setBrief] = useState("");

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">
            Panel
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

      <div className="mt-3 flex flex-col gap-3">
        {result.respondents.map((r) => (
          <div
            key={r.id}
            className="rounded-md border border-zinc-100 bg-zinc-50 p-3"
          >
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-xs text-zinc-500">{r.id}</span>
              <span className="text-sm font-medium text-zinc-900">
                {r.name}
              </span>
            </div>
            <ol className="mt-2 flex flex-col gap-1.5 text-sm text-zinc-700">
              {r.answers.map((a, i) => (
                <li key={i} className="flex gap-2">
                  <span className="shrink-0 text-zinc-500">
                    {a.itemIndex + 1}.
                  </span>
                  <div className="flex-1">
                    <div>{a.answer}</div>
                    {a.reasoning && (
                      <div className="text-xs text-zinc-500">
                        {a.reasoning}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>

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
            Regenerate panel with new context
          </label>
          <Textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={2}
            className="resize-none text-sm"
            placeholder="Describe how to adjust the panel…"
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

export function PanelResultCardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 text-xs text-zinc-500 shadow-sm">
      Simulating panel…
    </div>
  );
}
