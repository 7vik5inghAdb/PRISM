"use client";

import { useEffect, useRef } from "react";
import { type PrismUIMessage } from "@/lib/ai/ui-message";
import { Message } from "./message";

export function Thread({
  messages,
  onCardRegenerate,
}: {
  messages: PrismUIMessage[];
  onCardRegenerate: (messageId: string, prompt: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
        Start a research conversation…
      </div>
    );
  }
  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-6">
      {messages.map((m) => (
        <Message key={m.id} message={m} onCardRegenerate={onCardRegenerate} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
