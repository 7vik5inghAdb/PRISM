"use client";

import { useChat } from "@ai-sdk/react";
import { Composer } from "@/components/chat/composer";
import { Thread } from "@/components/chat/thread";
import { Button } from "@/components/ui/button";
import { type PrismUIMessage } from "@/lib/ai/ui-message";

export default function Home() {
  const { messages, sendMessage, status } = useChat<PrismUIMessage>();
  const isStreaming = status === "submitted" || status === "streaming";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
      <Thread messages={messages} />
      <div className="flex justify-center border-t border-zinc-200 p-2">
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
      </div>
      <Composer
        onSend={(text) => sendMessage({ text })}
        disabled={isStreaming}
      />
    </div>
  );
}
