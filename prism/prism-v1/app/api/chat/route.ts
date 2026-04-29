import { anthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";

export const runtime = "nodejs";

export async function GET() {
  const { text } = await generateText({
    model: anthropic("claude-opus-4-7"),
    prompt: "Say PRISM-OK.",
  });
  return Response.json({ text });
}
