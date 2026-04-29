import { anthropic } from "@ai-sdk/anthropic";
import { stepCountIs, streamText, type ModelMessage } from "ai";
import { MODELS } from "./models";
import { ORCHESTRATOR_SYSTEM } from "./prompts/orchestrator";
import { tools } from "./tools";

export function runOrchestrator({ messages }: { messages: ModelMessage[] }) {
  return streamText({
    model: anthropic(MODELS.orchestrator),
    system: ORCHESTRATOR_SYSTEM,
    messages,
    tools,
    stopWhen: stepCountIs(8),
  });
}
