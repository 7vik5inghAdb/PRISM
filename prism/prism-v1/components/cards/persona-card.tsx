"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { type Persona } from "@/lib/schemas/persona";

export function PersonaCard({
  persona,
  onRegenerate,
}: {
  persona: Persona;
  onRegenerate?: (brief: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [brief, setBrief] = useState("");

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">
            Persona
          </div>
          <div className="text-base font-medium text-zinc-900">
            {persona.name}
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

      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-zinc-600">
        <div>
          <dt className="inline text-zinc-500">Age </dt>
          <dd className="inline">{persona.demographics.ageRange}</dd>
        </div>
        <div>
          <dt className="inline text-zinc-500">Gender </dt>
          <dd className="inline">{persona.demographics.gender}</dd>
        </div>
        <div>
          <dt className="inline text-zinc-500">Location </dt>
          <dd className="inline">{persona.demographics.location}</dd>
        </div>
        <div>
          <dt className="inline text-zinc-500">Role </dt>
          <dd className="inline">{persona.demographics.occupation}</dd>
        </div>
      </dl>

      <Section title="Characteristics" items={persona.characteristics} />
      <Section title="Pain points" items={persona.painPoints} />
      <Section title="Goals" items={persona.goals} />

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
            Regenerate with new brief
          </label>
          <Textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={2}
            className="resize-none text-sm"
            placeholder="Describe the new persona target…"
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

export function PersonaCardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 text-xs text-zinc-500 shadow-sm">
      Generating persona…
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
        {items.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </div>
  );
}
