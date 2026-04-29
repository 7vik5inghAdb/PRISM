import {
  AggregatorCard,
  AggregatorCardSkeleton,
} from "@/components/cards/aggregator-card";
import { ChartCard, ChartCardSkeleton } from "@/components/cards/chart-card";
import {
  InstrumentCard,
  InstrumentCardSkeleton,
} from "@/components/cards/instrument-card";
import {
  ReportCard,
  ReportCardSkeleton,
} from "@/components/cards/report-card";
import {
  SecondaryResearchCard,
  SecondaryResearchCardSkeleton,
} from "@/components/cards/secondary-research-card";
import {
  PanelResultCard,
  PanelResultCardSkeleton,
} from "@/components/cards/panel-result-card";
import {
  PersonaCard,
  PersonaCardSkeleton,
} from "@/components/cards/persona-card";
import { PingCard } from "@/components/cards/ping-card";
import { type PrismUIMessage } from "@/lib/ai/ui-message";

export function Message({
  message,
  onCardRegenerate,
}: {
  message: PrismUIMessage;
  onCardRegenerate: (messageId: string, prompt: string) => void;
}) {
  const isUser = message.role === "user";
  return (
    <div
      className={`flex flex-col gap-2 ${
        isUser ? "items-end" : "items-start"
      }`}
    >
      {message.parts.map((part, i) => {
        if (part.type === "text") {
          return (
            <div
              key={i}
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                isUser
                  ? "bg-zinc-900 text-zinc-50"
                  : "bg-zinc-100 text-zinc-900"
              }`}
            >
              <span className="whitespace-pre-wrap">{part.text}</span>
            </div>
          );
        }
        if (part.type === "data-ping-card") {
          return (
            <div key={i} className="w-full max-w-[80%]">
              <PingCard {...part.data} />
            </div>
          );
        }
        if (part.type === "tool-personaGenerator") {
          if (
            part.state === "input-streaming" ||
            part.state === "input-available"
          ) {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <PersonaCardSkeleton />
              </div>
            );
          }
          if (part.state === "output-available") {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <PersonaCard
                  persona={part.output}
                  onRegenerate={(brief) =>
                    onCardRegenerate(
                      message.id,
                      `Regenerate the persona with this updated brief: ${brief}`,
                    )
                  }
                />
              </div>
            );
          }
          if (part.state === "output-error") {
            return (
              <div
                key={i}
                className="w-full max-w-[80%] rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                Persona generation failed: {part.errorText}
              </div>
            );
          }
          return null;
        }
        if (part.type === "tool-instrumentDesigner") {
          if (
            part.state === "input-streaming" ||
            part.state === "input-available"
          ) {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <InstrumentCardSkeleton />
              </div>
            );
          }
          if (part.state === "output-available") {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <InstrumentCard
                  instrument={part.output}
                  onRegenerate={(brief) =>
                    onCardRegenerate(
                      message.id,
                      `Regenerate the instrument with these updates: ${brief}`,
                    )
                  }
                />
              </div>
            );
          }
          if (part.state === "output-error") {
            return (
              <div
                key={i}
                className="w-full max-w-[80%] rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                Instrument design failed: {part.errorText}
              </div>
            );
          }
          return null;
        }
        if (part.type === "tool-panelSimulator") {
          if (
            part.state === "input-streaming" ||
            part.state === "input-available"
          ) {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <PanelResultCardSkeleton />
              </div>
            );
          }
          if (part.state === "output-available") {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <PanelResultCard
                  result={part.output}
                  onRegenerate={(brief) =>
                    onCardRegenerate(
                      message.id,
                      `Regenerate the panel with these updates: ${brief}`,
                    )
                  }
                />
              </div>
            );
          }
          if (part.state === "output-error") {
            return (
              <div
                key={i}
                className="w-full max-w-[80%] rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                Panel simulation failed: {part.errorText}
              </div>
            );
          }
          return null;
        }
        if (part.type === "tool-aggregator") {
          if (
            part.state === "input-streaming" ||
            part.state === "input-available"
          ) {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <AggregatorCardSkeleton />
              </div>
            );
          }
          if (part.state === "output-available") {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <AggregatorCard
                  result={part.output}
                  onRegenerate={(brief) =>
                    onCardRegenerate(
                      message.id,
                      `Re-aggregate with this emphasis: ${brief}`,
                    )
                  }
                />
              </div>
            );
          }
          if (part.state === "output-error") {
            return (
              <div
                key={i}
                className="w-full max-w-[80%] rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                Aggregation failed: {part.errorText}
              </div>
            );
          }
          return null;
        }
        if (part.type === "tool-chartBuilder") {
          if (
            part.state === "input-streaming" ||
            part.state === "input-available"
          ) {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <ChartCardSkeleton />
              </div>
            );
          }
          if (part.state === "output-available") {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <ChartCard
                  spec={part.output}
                  onRegenerate={(brief) =>
                    onCardRegenerate(
                      message.id,
                      `Re-chart with this focus: ${brief}`,
                    )
                  }
                />
              </div>
            );
          }
          if (part.state === "output-error") {
            return (
              <div
                key={i}
                className="w-full max-w-[80%] rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                Chart build failed: {part.errorText}
              </div>
            );
          }
          return null;
        }
        if (part.type === "tool-secondaryResearch") {
          if (
            part.state === "input-streaming" ||
            part.state === "input-available"
          ) {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <SecondaryResearchCardSkeleton />
              </div>
            );
          }
          if (part.state === "output-available") {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <SecondaryResearchCard
                  result={part.output}
                  onRegenerate={(brief) =>
                    onCardRegenerate(
                      message.id,
                      `Re-research with this update: ${brief}`,
                    )
                  }
                />
              </div>
            );
          }
          if (part.state === "output-error") {
            return (
              <div
                key={i}
                className="w-full max-w-[80%] rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                Secondary research failed: {part.errorText}
              </div>
            );
          }
          return null;
        }
        if (part.type === "tool-reportCompiler") {
          if (
            part.state === "input-streaming" ||
            part.state === "input-available"
          ) {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <ReportCardSkeleton />
              </div>
            );
          }
          if (part.state === "output-available") {
            return (
              <div key={i} className="w-full max-w-[80%]">
                <ReportCard
                  report={part.output}
                  onRegenerate={(brief) =>
                    onCardRegenerate(
                      message.id,
                      `Re-compile the report with this emphasis: ${brief}`,
                    )
                  }
                />
              </div>
            );
          }
          if (part.state === "output-error") {
            return (
              <div
                key={i}
                className="w-full max-w-[80%] rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700"
              >
                Report compilation failed: {part.errorText}
              </div>
            );
          }
          return null;
        }
        return null;
      })}
    </div>
  );
}
