import { type UIMessage } from "ai";

export type PrismDataParts = {
  "ping-card": { id: string; ts: string; label: string };
};

export type PrismUIMessage = UIMessage<unknown, PrismDataParts>;
