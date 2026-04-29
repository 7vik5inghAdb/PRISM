"use client";

import { useChat } from "@ai-sdk/react";
import { Composer } from "@/components/chat/composer";
import { Thread } from "@/components/chat/thread";
import { Button } from "@/components/ui/button";
import { type PrismUIMessage } from "@/lib/ai/ui-message";

export default function Home() {
  const {
    messages,
    sendMessage,
    setMessages,
    status,
    error,
    clearError,
  } = useChat<PrismUIMessage>();
  const isStreaming = status === "submitted" || status === "streaming";

  function onCardRegenerate(messageId: string, prompt: string) {
    setMessages((msgs) => msgs.filter((m) => m.id !== messageId));
    sendMessage({ text: prompt });
  }

  async function newRun() {
    if (
      !window.confirm("Start a new run? This clears the current conversation.")
    ) {
      return;
    }
    setMessages([]);
    clearError();
    await fetch("/api/runs", { method: "DELETE" });
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
      <Thread messages={messages} onCardRegenerate={onCardRegenerate} />
      {error && (
        <div className="flex items-start justify-between gap-3 border-t border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          <span className="flex-1 whitespace-pre-wrap">{error.message}</span>
          <button
            type="button"
            className="shrink-0 text-xs underline underline-offset-2"
            onClick={clearError}
          >
            Dismiss
          </button>
        </div>
      )}
      <div className="flex justify-center gap-2 border-t border-zinc-200 p-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isStreaming}
          onClick={() =>
            sendMessage(
              { text: "Show me a test card." },
              { body: { ping: true } },
            )
          }
        >
          Send ping card
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={isStreaming}
          onClick={newRun}
        >
          New run
        </Button>
      </div>
      <Composer
        onSend={(text) => sendMessage({ text })}
        disabled={isStreaming}
      />
    </div>
  );
}
