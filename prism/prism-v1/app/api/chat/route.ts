import { anthropic } from "@ai-sdk/anthropic";
import {
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  streamText,
  type UIMessage,
} from "ai";
import { type PrismUIMessage } from "@/lib/ai/ui-message";
import { persistMessages } from "@/lib/db/runs";

export const runtime = "nodejs";

const RUN_ID = "current";

export async function POST(req: Request) {
  const body: { messages: UIMessage[]; ping?: boolean } = await req.json();
  const originalMessages = body.messages as PrismUIMessage[];

  if (body.ping === true) {
    const stream = createUIMessageStream<PrismUIMessage>({
      originalMessages,
      execute: ({ writer }) => {
        writer.write({
          type: "data-ping-card",
          data: {
            id: `ping-${Date.now()}`,
            ts: new Date().toISOString(),
            label: "Generative UI works.",
          },
        });
      },
      onFinish: async ({ messages }) => {
        await persistMessages(RUN_ID, messages);
      },
    });
    return createUIMessageStreamResponse({ stream });
  }

  const result = streamText({
    model: anthropic("claude-opus-4-7"),
    messages: await convertToModelMessages(originalMessages),
  });
  return result.toUIMessageStreamResponse<PrismUIMessage>({
    originalMessages,
    onFinish: async ({ messages }) => {
      await persistMessages(RUN_ID, messages);
    },
  });
}
