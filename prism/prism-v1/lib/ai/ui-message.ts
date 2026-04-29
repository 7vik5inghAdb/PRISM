import { type InferUITools, type UIMessage } from "ai";
import { type tools } from "./tools";

export type PrismDataParts = {
  "ping-card": { id: string; ts: string; label: string };
};

export type PrismTools = InferUITools<typeof tools>;

export type PrismUIMessage = UIMessage<unknown, PrismDataParts, PrismTools>;
