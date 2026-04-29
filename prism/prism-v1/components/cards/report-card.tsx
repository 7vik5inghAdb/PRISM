"use client";

import { useRef, useState } from "react";
import { useReactToPrint } from "react-to-print";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { type Report } from "@/lib/schemas/report";

export function ReportCard({
  report,
  onRegenerate,
}: {
  report: Report;
  onRegenerate?: (brief: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [brief, setBrief] = useState("");
  const printRef = useRef<HTMLDivElement>(null);
  const handlePrint = useReactToPrint({
    contentRef: printRef,
    documentTitle: report.title,
  });

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">
            Report
          </div>
          <div className="text-base font-medium text-zinc-900">
            {report.title}
          </div>
        </div>
        <div className="flex gap-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => handlePrint()}
          >
            Export PDF
          </Button>
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
      </div>

      <div
        ref={printRef}
        className="mt-3 flex flex-col gap-4 p-1 text-sm text-zinc-800 print:p-8 print:text-zinc-900"
      >
        <header className="border-b border-zinc-200 pb-3 print:border-zinc-300">
          <h1 className="text-lg font-semibold text-zinc-900 print:text-2xl">
            {report.title}
          </h1>
          <div className="mt-1 text-xs text-zinc-500">{report.date}</div>
          {report.hypothesis && (
            <div className="mt-2 text-xs italic text-zinc-600">
              Hypothesis: {report.hypothesis}
            </div>
          )}
        </header>

        <section>
          <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Executive summary
          </h2>
          <p className="mt-1 whitespace-pre-wrap">{report.executiveSummary}</p>
        </section>

        {report.sections.map((s, i) => (
          <section key={i}>
            <h2 className="text-sm font-semibold text-zinc-900">{s.heading}</h2>
            <div className="mt-1 whitespace-pre-wrap">{s.body}</div>
          </section>
        ))}

        {report.recommendations.length > 0 && (
          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Recommendations
            </h2>
            <ol className="mt-1 list-inside list-decimal">
              {report.recommendations.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ol>
          </section>
        )}
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
            Re-compile with new emphasis
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

export function ReportCardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 text-xs text-zinc-500 shadow-sm">
      Compiling report…
    </div>
  );
}
