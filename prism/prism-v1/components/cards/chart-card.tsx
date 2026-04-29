"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { type ChartDataPoint, type ChartSpec } from "@/lib/schemas/chart";

export function ChartCard({
  spec,
  onRegenerate,
}: {
  spec: ChartSpec;
  onRegenerate?: (brief: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [brief, setBrief] = useState("");
  const max = Math.max(0, ...spec.data.map((d) => d.value)) || 1;

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">
            Chart
          </div>
          <div className="text-base font-medium text-zinc-900">
            {spec.title}
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

      {spec.description && (
        <p className="mt-2 text-sm text-zinc-700">{spec.description}</p>
      )}

      <div className="mt-3">
        {spec.chartType === "bar" ? (
          <BarChart data={spec.data} max={max} />
        ) : (
          <HorizontalBarChart data={spec.data} max={max} />
        )}
      </div>

      {(spec.xAxisLabel || spec.yAxisLabel) && (
        <div className="mt-2 flex justify-between text-[10px] uppercase tracking-wide text-zinc-500">
          <span>{spec.xAxisLabel ?? ""}</span>
          <span>{spec.yAxisLabel ?? ""}</span>
        </div>
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
            Re-chart with new focus
          </label>
          <Textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={2}
            className="resize-none text-sm"
            placeholder="Describe what to chart instead…"
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

export function ChartCardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 text-xs text-zinc-500 shadow-sm">
      Building chart…
    </div>
  );
}

function BarChart({ data, max }: { data: ChartDataPoint[]; max: number }) {
  return (
    <div className="flex h-40 items-end gap-2">
      {data.map((d, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <div
            className="w-full rounded-t bg-zinc-800"
            style={{ height: `${(d.value / max) * 100}%` }}
            title={`${d.label}: ${d.value}`}
          />
          <div className="w-full truncate text-center text-[10px] text-zinc-600">
            {d.label}
          </div>
          <div className="text-[10px] text-zinc-500">{d.value}</div>
        </div>
      ))}
    </div>
  );
}

function HorizontalBarChart({
  data,
  max,
}: {
  data: ChartDataPoint[];
  max: number;
}) {
  return (
    <div className="flex flex-col gap-2">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <div className="w-28 truncate text-right text-zinc-700">
            {d.label}
          </div>
          <div className="relative h-5 flex-1 rounded bg-zinc-100">
            <div
              className="absolute inset-y-0 left-0 rounded bg-zinc-800"
              style={{ width: `${(d.value / max) * 100}%` }}
              title={`${d.value}`}
            />
          </div>
          <div className="w-10 text-right text-zinc-700">{d.value}</div>
        </div>
      ))}
    </div>
  );
}
